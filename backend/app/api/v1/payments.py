"""Payment webhook routes."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request as FastAPIRequest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.db.models import Payment, PaymentEvent, Request, RequestStatusEvent
from app.services.letters.email_service import send_request_status_email
from app.services.letters.payment_service import verify_stripe_webhook

router = APIRouter()


@router.post("/webhook/stripe")
async def stripe_webhook(
    request: FastAPIRequest,
    db: Session = Depends(get_db),
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> dict:
    payload = await request.body()
    try:
        event = verify_stripe_webhook(payload, stripe_signature)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})
    payment_intent_id = data_object.get("id")
    payment = db.scalar(select(Payment).where(Payment.provider_checkout_id == payment_intent_id))
    if payment is None:
        return {"status": "ignored"}

    db.add(
        PaymentEvent(
            payment_id=payment.id,
            provider_event_id=event.get("id", payment_intent_id),
            event_type=event_type or "unknown",
            payload_json=event,
            processed_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )

    req = db.get(Request, payment.request_id)
    if req is None:
        db.commit()
        return {"status": "processed"}

    if event_type == "payment_intent.succeeded":
        payment.status = "paid"
        payment.provider_payment_id = payment_intent_id
        payment.paid_at = datetime.now(UTC).replace(tzinfo=None)
        req.payment_status = "paid"
        if req.status == "payment_pending":
            req.status = "paid"
            req.paid_at = payment.paid_at
            db.add(
                RequestStatusEvent(
                    request_id=req.id,
                    from_status="payment_pending",
                    to_status="paid",
                    reason_code="stripe_webhook_paid",
                    reason_text="Payment confirmed by Stripe webhook",
                    acted_by_user_id=None,
                )
            )
    elif event_type == "payment_intent.payment_failed":
        payment.status = "failed"
        payment.failure_message = data_object.get("last_payment_error", {}).get("message")
    db.commit()
    if event_type == "payment_intent.succeeded" and req.status == "paid":
        try:
            send_request_status_email(db, request=req)
            db.commit()
        except Exception:
            db.rollback()
    return {"status": "processed"}
