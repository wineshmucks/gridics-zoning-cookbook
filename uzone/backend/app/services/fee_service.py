"""Fee and quoting helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FeeSchedule, FeeScheduleItem, Quote, Request


def resolve_active_fee_schedule(db: Session, jurisdiction_id: str) -> FeeSchedule | None:
    now = datetime.now(UTC).replace(tzinfo=None)
    return db.scalar(
        select(FeeSchedule)
        .where(
            FeeSchedule.jurisdiction_id == jurisdiction_id,
            FeeSchedule.status == "active",
            (FeeSchedule.effective_start_at.is_(None) | (FeeSchedule.effective_start_at <= now)),
            (FeeSchedule.effective_end_at.is_(None) | (FeeSchedule.effective_end_at >= now)),
        )
        .order_by(FeeSchedule.created_at.desc())
    )


def build_quote_for_request(db: Session, request: Request) -> Quote:
    fee_schedule = resolve_active_fee_schedule(db, request.jurisdiction_id)
    if fee_schedule is None:
        raise ValueError("No active fee schedule found for jurisdiction")

    items = db.scalars(
        select(FeeScheduleItem).where(
            FeeScheduleItem.fee_schedule_id == fee_schedule.id,
            FeeScheduleItem.is_active.is_(True),
        )
    ).all()

    line_items: list[dict] = []
    subtotal_cents = 0
    tax_cents = 0
    for item in items:
        if item.applies_to_letter_type and item.applies_to_letter_type != request.letter_type:
            continue
        if item.applies_to_processing_type and item.applies_to_processing_type != request.processing_type:
            continue
        if item.applies_to_delivery_method and item.applies_to_delivery_method != request.delivery_method:
            continue

        subtotal_cents += item.amount_cents
        line_items.append(
            {
                "code": item.code,
                "name": item.name,
                "amount_cents": item.amount_cents,
                "currency": item.currency,
            }
        )

    quote = Quote(
        request_id=request.id,
        fee_schedule_id=fee_schedule.id,
        status="finalized",
        line_items_json=line_items,
        subtotal_cents=subtotal_cents,
        tax_cents=tax_cents,
        total_cents=subtotal_cents + tax_cents,
        currency="USD",
        expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=7),
    )
    return quote
