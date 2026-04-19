"""Utilities for third-party embed authentication and widget sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import secrets
from typing import Any
from urllib.parse import urlsplit

import jwt
from fastapi import HTTPException, status

from app.core.config import settings
from app.db.models import TenantClient
from app.services.tenant_service import get_tenant_logo_path

EMBED_SETTINGS_KEY = "assistant_embed"
EMBED_SECRET_HASH_SETTING_KEY = "secret_hash"
EMBED_ALLOWED_ORIGINS_SETTING_KEY = "allowed_origins"
EMBED_WIDGET_TITLE_SETTING_KEY = "widget_title"
EMBED_LAUNCHER_LABEL_SETTING_KEY = "launcher_label"
EMBED_ACCENT_COLOR_SETTING_KEY = "accent_color"
EMBED_IS_ACTIVE_SETTING_KEY = "is_active"
EMBED_CREATED_AT_SETTING_KEY = "created_at"
EMBED_UPDATED_AT_SETTING_KEY = "updated_at"
EMBED_SECRET_PREFIX = "uze_"


@dataclass(slots=True)
class TenantEmbedSettings:
    secret_hash: str | None
    allowed_origins: list[str]
    widget_title: str | None
    launcher_label: str | None
    accent_color: str | None
    is_active: bool
    created_at: str | None
    updated_at: str | None


def normalize_embed_origin(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value.strip())
    if not parsed.scheme or not parsed.hostname:
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    host = parsed.hostname.lower()
    if parsed.port:
        return f"{parsed.scheme.lower()}://{host}:{parsed.port}"
    return f"{parsed.scheme.lower()}://{host}"


def normalize_embed_origin_list(values: object) -> list[str]:
    if isinstance(values, str):
        raw_values = [values]
    elif isinstance(values, list):
        raw_values = [str(item) for item in values if isinstance(item, str) and item.strip()]
    else:
        return []

    normalized: list[str] = []
    for raw_value in raw_values:
        normalized_value = normalize_embed_origin(raw_value)
        if normalized_value and normalized_value not in normalized:
            normalized.append(normalized_value)
    return normalized


def _normalize_embed_color(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def get_tenant_embed_settings(settings_json: dict | None) -> TenantEmbedSettings:
    if not isinstance(settings_json, dict):
        return TenantEmbedSettings(
            secret_hash=None,
            allowed_origins=[],
            widget_title=None,
            launcher_label=None,
            accent_color=None,
            is_active=False,
            created_at=None,
            updated_at=None,
        )

    raw_embed = settings_json.get(EMBED_SETTINGS_KEY)
    raw_embed_dict = raw_embed if isinstance(raw_embed, dict) else {}
    allowed_origins = normalize_embed_origin_list(raw_embed_dict.get(EMBED_ALLOWED_ORIGINS_SETTING_KEY))
    return TenantEmbedSettings(
        secret_hash=raw_embed_dict.get(EMBED_SECRET_HASH_SETTING_KEY)
        if isinstance(raw_embed_dict.get(EMBED_SECRET_HASH_SETTING_KEY), str)
        else None,
        allowed_origins=allowed_origins,
        widget_title=_coerce_optional_str(raw_embed_dict.get(EMBED_WIDGET_TITLE_SETTING_KEY)),
        launcher_label=_coerce_optional_str(raw_embed_dict.get(EMBED_LAUNCHER_LABEL_SETTING_KEY)),
        accent_color=_normalize_embed_color(raw_embed_dict.get(EMBED_ACCENT_COLOR_SETTING_KEY)),
        is_active=bool(raw_embed_dict.get(EMBED_IS_ACTIVE_SETTING_KEY, False)),
        created_at=_coerce_optional_str(raw_embed_dict.get(EMBED_CREATED_AT_SETTING_KEY)),
        updated_at=_coerce_optional_str(raw_embed_dict.get(EMBED_UPDATED_AT_SETTING_KEY)),
    )


def _coerce_optional_str(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def merge_tenant_embed_settings(
    existing_settings: dict | None,
    *,
    secret_hash: str | None = None,
    allowed_origins: list[str] | None = None,
    widget_title: str | None = None,
    launcher_label: str | None = None,
    accent_color: str | None = None,
    is_active: bool | None = None,
) -> dict:
    next_settings = dict(existing_settings) if isinstance(existing_settings, dict) else {}
    current_raw = next_settings.get(EMBED_SETTINGS_KEY)
    current = current_raw if isinstance(current_raw, dict) else {}
    merged = dict(current)

    if secret_hash is not None:
        merged[EMBED_SECRET_HASH_SETTING_KEY] = secret_hash or None
    if allowed_origins is not None:
        merged[EMBED_ALLOWED_ORIGINS_SETTING_KEY] = normalize_embed_origin_list(allowed_origins)
    if widget_title is not None:
        merged[EMBED_WIDGET_TITLE_SETTING_KEY] = widget_title.strip() or None
    if launcher_label is not None:
        merged[EMBED_LAUNCHER_LABEL_SETTING_KEY] = launcher_label.strip() or None
    if accent_color is not None:
        merged[EMBED_ACCENT_COLOR_SETTING_KEY] = accent_color.strip() or None
    if is_active is not None:
        merged[EMBED_IS_ACTIVE_SETTING_KEY] = bool(is_active)

    if any(value is not None for value in merged.values()):
        merged[EMBED_CREATED_AT_SETTING_KEY] = (
            merged.get(EMBED_CREATED_AT_SETTING_KEY)
            or current.get(EMBED_CREATED_AT_SETTING_KEY)
            or datetime.now(UTC).isoformat()
        )
        merged[EMBED_UPDATED_AT_SETTING_KEY] = datetime.now(UTC).isoformat()
        next_settings[EMBED_SETTINGS_KEY] = merged
    else:
        next_settings.pop(EMBED_SETTINGS_KEY, None)

    return next_settings


def generate_embed_secret() -> str:
    return f"{EMBED_SECRET_PREFIX}{secrets.token_urlsafe(32)}"


def hash_embed_secret(secret: str) -> str:
    normalized = secret.strip().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def verify_embed_secret(secret: str, secret_hash: str | None) -> bool:
    if not secret_hash:
        return False
    return hmac.compare_digest(hash_embed_secret(secret), secret_hash)


def require_embed_signing_secret() -> str:
    signing_secret = settings.embed_session_signing_secret.strip() if settings.embed_session_signing_secret else ""
    if not signing_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embed session signing secret is not configured.",
        )
    return signing_secret


def issue_embed_session_token(
    *,
    tenant_client: TenantClient,
    embed_origin: str,
    assistant_disclaimer_text: str | None,
    widget_title: str | None,
    launcher_label: str | None,
    accent_color: str | None,
) -> tuple[str, datetime]:
    expires_at = datetime.now(UTC) + timedelta(seconds=max(60, int(settings.embed_session_ttl_seconds)))
    payload = {
        "iss": settings.embed_session_issuer,
        "aud": settings.embed_session_audience,
        "sub": tenant_client.client_id,
        "client_id": tenant_client.client_id,
        "city_name": tenant_client.city_name,
        "department_name": tenant_client.department_name,
        "logo_path": get_tenant_logo_path(getattr(tenant_client, "settings_json", None)),
        "assistant_disclaimer_text": assistant_disclaimer_text,
        "origin": embed_origin,
        "widget_title": widget_title,
        "launcher_label": launcher_label,
        "accent_color": accent_color,
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": secrets.token_urlsafe(16),
    }
    token = jwt.encode(payload, require_embed_signing_secret(), algorithm="HS256")
    return token, expires_at


def decode_embed_session_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            require_embed_signing_secret(),
            algorithms=["HS256"],
            audience=settings.embed_session_audience,
            issuer=settings.embed_session_issuer,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid embed session token") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid embed session token")

    return payload


def parse_embed_token_from_header(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing embed token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid embed token header")
    return token


def build_embed_widget_payload(
    *,
    tenant_client: TenantClient,
    embed_settings: TenantEmbedSettings,
    token: str,
    expires_at: datetime,
    assistant_disclaimer_text: str | None,
    embed_origin: str | None,
) -> dict[str, Any]:
    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
        "client_id": tenant_client.client_id,
        "city_name": tenant_client.city_name,
        "department_name": tenant_client.department_name,
        "logo_path": get_tenant_logo_path(getattr(tenant_client, "settings_json", None)),
        "assistant_disclaimer_text": assistant_disclaimer_text,
        "widget_title": embed_settings.widget_title or f"Ask {tenant_client.city_name}",
        "launcher_label": embed_settings.launcher_label or "Have a question?",
        "accent_color": embed_settings.accent_color or "#0b67c2",
        "allowed_origins": embed_settings.allowed_origins,
        "origin": embed_origin,
    }


def sanitize_embed_widget_payload(payload: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "client_id",
        "city_name",
        "department_name",
        "logo_path",
        "assistant_disclaimer_text",
        "widget_title",
        "launcher_label",
        "accent_color",
        "allowed_origins",
        "origin",
        "expires_at",
    }
    return {key: value for key, value in payload.items() if key in allowed_keys}
