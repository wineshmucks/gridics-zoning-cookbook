"""Reporting routes."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.db.models import Request
from app.schemas import ReportSummary


router = APIRouter()


@router.get("/summary", response_model=ReportSummary)
def reports_summary(db: Session = Depends(get_db)) -> ReportSummary:
    total_requests = db.scalar(select(func.count()).select_from(Request)) or 0
    total_revenue_cents = (
        db.scalar(select(func.coalesce(func.sum(Request.total_amount_cents), 0)).where(Request.payment_status == "paid"))
        or 0
    )
    def count_by_status(status: str) -> int:
        return db.scalar(select(func.count()).select_from(Request).where(Request.status == status)) or 0

    return ReportSummary(
        total_requests=total_requests,
        submitted_requests=count_by_status("submitted"),
        paid_requests=count_by_status("paid"),
        in_progress_requests=count_by_status("in_progress"),
        approved_requests=count_by_status("approved"),
        delivered_requests=count_by_status("delivered"),
        total_revenue_cents=total_revenue_cents,
    )
