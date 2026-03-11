"""Unit tests for quote generation."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import FeeSchedule, FeeScheduleItem, Request
from app.services.fee_service import build_quote_for_request


def _db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()


def test_build_quote_for_request_matches_applicable_items() -> None:
    db = _db()
    try:
        schedule = FeeSchedule(
            id="sched-1",
            jurisdiction_id="jur-1",
            name="Default",
            status="active",
            effective_start_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1),
        )
        db.add(schedule)
        db.add_all(
            [
                FeeScheduleItem(
                    fee_schedule_id=schedule.id,
                    code="base-standard",
                    name="Base Standard",
                    fee_type="base",
                    amount_cents=7500,
                    applies_to_letter_type="standard",
                    currency="USD",
                ),
                FeeScheduleItem(
                    fee_schedule_id=schedule.id,
                    code="rush",
                    name="Rush",
                    fee_type="addon",
                    amount_cents=5000,
                    applies_to_processing_type="expedited",
                    currency="USD",
                ),
                FeeScheduleItem(
                    fee_schedule_id=schedule.id,
                    code="mail",
                    name="Mail",
                    fee_type="addon",
                    amount_cents=1500,
                    applies_to_delivery_method="mail",
                    currency="USD",
                ),
            ]
        )
        request = Request(
            id="req-1",
            public_id="ZVL-2026-000001",
            jurisdiction_id="jur-1",
            requester_user_id="user-1",
            property_id="prop-1",
            property_snapshot_id="snap-1",
            letter_type="standard",
            processing_type="expedited",
            delivery_method="mail",
            status="submitted",
            payment_status="unpaid",
            requester_first_name="A",
            requester_last_name="B",
            requester_email="a@example.com",
            total_amount_cents=0,
            currency="USD",
        )
        db.add(request)
        db.commit()

        quote = build_quote_for_request(db, request)
        assert quote.total_cents == 14000
        assert len(quote.line_items_json) == 3
    finally:
        db.close()
