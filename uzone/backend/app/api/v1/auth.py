"""Authentication routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, sync_user_from_auth
from app.core.config import settings
from app.core.security import AuthContext, require_auth
from app.db.models import Session as UserSession
from app.db.models import User
from app.schemas import AuthSessionRead, LoginRequest, RegisterRequest, UserRead
from app.services.auth_service import (
    hash_password,
    hash_session_token,
    new_session_token,
    session_expiry,
    verify_password,
)

router = APIRouter()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> UserRead:
    if settings.auth_provider == "clerk":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Local registration is disabled when auth_provider=clerk",
        )
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        organization=payload.organization,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


@router.post("/login", response_model=AuthSessionRead)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthSessionRead:
    if settings.auth_provider == "clerk":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Local login is disabled when auth_provider=clerk. Use Clerk on the frontend.",
        )
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    raw_token = new_session_token()
    expires_at = session_expiry()
    session = UserSession(
        user_id=user.id,
        token_hash=hash_session_token(raw_token),
        expires_at=expires_at.replace(tzinfo=None),
    )
    db.add(session)
    user.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return AuthSessionRead(
        token=raw_token,
        expires_at=expires_at,
        user=UserRead.model_validate(user),
    )


@router.get("/me")
def me(auth: AuthContext = Depends(require_auth), db: Session = Depends(get_db)) -> dict:
    local_user_id = None
    if auth.provider == "clerk":
        local_user = sync_user_from_auth(db, auth)
        local_user_id = local_user.id
    return {
        "auth_provider": auth.provider,
        "user_id": auth.user_id,
        "session_id": auth.session_id,
        "email": auth.email,
        "local_user_id": local_user_id,
    }
