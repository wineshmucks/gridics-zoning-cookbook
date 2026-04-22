"""Shared FastAPI dependencies."""

from collections.abc import Generator
import re

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import AuthContext, optional_auth
from app.db.models import User
from app.db.session import SessionLocal
from app.services.shared.auth_service import hash_password


def _fallback_clerk_email(user_id: str) -> str:
    safe_user_id = re.sub(r"[^a-zA-Z0-9._+-]", "-", user_id)
    return f"{safe_user_id}@users.uzone.example.com"


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_optional_auth_context(auth: AuthContext | None = Depends(optional_auth)) -> AuthContext | None:
    return auth


def sync_user_from_auth(db: Session, auth: AuthContext) -> User:
    if auth.provider != "clerk" or not auth.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unsupported auth context")

    user = db.query(User).filter(User.clerk_user_id == auth.user_id).one_or_none()
    if user is not None:
        return user

    email = auth.email or _fallback_clerk_email(auth.user_id)
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is not None:
        user.clerk_user_id = auth.user_id
        db.commit()
        db.refresh(user)
        return user

    user = User(
        email=email,
        clerk_user_id=auth.user_id,
        password_hash=hash_password(auth.user_id),
        first_name=auth.first_name or "Clerk",
        last_name=auth.last_name or "User",
        organization="Clerk",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def resolve_actor_user(
    db: Session,
    *,
    explicit_user_id: str | None,
    auth: AuthContext | None,
) -> User:
    if auth is not None and auth.provider == "clerk":
        user = sync_user_from_auth(db, auth)
        if explicit_user_id and explicit_user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Authenticated Clerk user does not match payload actor",
            )
        return user

    if explicit_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="actor_user_id is required when auth is not managed by Clerk",
        )

    user = db.get(User, explicit_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Actor user not found")
    return user
