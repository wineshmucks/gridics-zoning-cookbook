"""Authentication helpers including Clerk session token verification."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import httpx
import jwt
from fastapi import Header, HTTPException, status

from app.core.config import settings


@dataclass
class AuthContext:
    user_id: str | None
    session_id: str | None
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    provider: str = "local"


@lru_cache(maxsize=1)
def _clerk_public_keys() -> list[str]:
    if settings.clerk_pem_public_key:
        return [settings.clerk_pem_public_key]
    try:
        response = httpx.get(settings.clerk_jwks_url, timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Clerk JWKS endpoint rejected the backend request. Check CLERK_JWKS_URL or CLERK_PEM_PUBLIC_KEY.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to fetch Clerk JWKS",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to reach Clerk JWKS",
        ) from exc
    jwks = response.json()
    keys: list[str] = []
    for jwk in jwks.get("keys", []):
        keys.append(jwt.algorithms.RSAAlgorithm.from_jwk(jwk))
    if not keys:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Clerk JWKS did not return any signing keys",
        )
    return keys


def verify_clerk_token(token: str) -> AuthContext:
    authorized_parties = [item.strip() for item in settings.clerk_authorized_parties.split(",") if item.strip()]
    last_error: Exception | None = None
    for public_key in _clerk_public_keys():
        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                options={"verify_aud": False},
            )
            azp = payload.get("azp")
            if authorized_parties and azp and azp not in authorized_parties:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token authorized party is not allowed",
                )
            if payload.get("sts") == "pending":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Clerk session is pending",
                )
            return AuthContext(
                user_id=payload.get("sub"),
                session_id=payload.get("sid"),
                email=payload.get("email"),
                first_name=payload.get("given_name"),
                last_name=payload.get("family_name"),
                provider="clerk",
            )
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - external verification
            last_error = exc
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Invalid Clerk token: {last_error}",
    )


def auth_context_from_headers(authorization: str | None) -> AuthContext:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header")
    if settings.auth_provider == "clerk":
        return verify_clerk_token(token)
    return AuthContext(user_id=None, session_id=None, provider="local")


def require_auth(authorization: str | None = Header(default=None)) -> AuthContext:
    return auth_context_from_headers(authorization)


def optional_auth(authorization: str | None = Header(default=None)) -> AuthContext | None:
    if not authorization:
        return None
    return auth_context_from_headers(authorization)
