"""Development-only helper routes."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import settings
from app.db.models import User
from fastapi import Depends

router = APIRouter()


@router.get("/identities")
def dev_identities(db: Session = Depends(get_db)) -> dict:
    if settings.auth_provider != "local":
        raise HTTPException(status_code=404, detail="Not available")
    users = db.scalars(select(User).order_by(User.created_at.asc())).all()
    by_email = {user.email: user.id for user in users}
    return {
        "admin_user_id": by_email.get("admin@uzone.example.com"),
        "staff_user_id": by_email.get("staff@uzone.example.com"),
        "customer_user_id": by_email.get("customer@uzone.example.com"),
    }
