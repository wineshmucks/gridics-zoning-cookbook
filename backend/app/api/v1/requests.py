"""Public request routes."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_optional_auth_context, resolve_actor_user
from app.core.security import AuthContext
from app.domain.request_states import ensure_transition_allowed
from app.db.models import (
    Jurisdiction,
    Payment,
    Property,
    PropertySnapshot,
    Quote,
    Request,
    RequestStatusEvent,
    User,
)
from app.schemas import (
    PaymentCheckoutCreate,
    PaymentRead,
    QuoteRead,
    RequestCreate,
    RequestPaymentConfirm,
    RequestRead,
    RequestStatusEventRead,
    RequestSubmit,
)
from app.services.letters.email_service import send_request_status_email
from app.services.letters.fee_service import build_quote_for_request
from app.services.letters.payment_service import get_payment_provider

router = APIRouter()


def _request_public_id(db: Session) -> str:
    year = datetime.now(UTC).year
    latest = db.scalars(select(Request.public_id).where(Request.public_id.like(f"ZVL-{year}-%"))).all()
    if not latest:
        return f"ZVL-{year}-000001"
    next_number = max(int(item.rsplit("-", 1)[-1]) for item in latest) + 1
    return f"ZVL-{year}-{next_number:06d}"


def _load_request(db: Session, request_id: str) -> Request | None:
    request = db.get(Request, request_id)
    if request is None:
        request = db.scalar(select(Request).where(Request.public_id == request_id))
    return request


@router.post("", response_model=RequestRead, status_code=status.HTTP_201_CREATED)
def create_request(payload: RequestCreate, db: Session = Depends(get_db)) -> RequestRead:
    jurisdiction = db.get(Jurisdiction, payload.jurisdiction_id)
    if jurisdiction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jurisdiction not found")

    requester = db.get(User, payload.requester_user_id)
    if requester is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requester not found")

    property_record = db.get(Property, payload.property_id)
    if property_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    if property_record.jurisdiction_id != jurisdiction.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Property does not belong to the specified jurisdiction",
        )

    property_snapshot = db.get(PropertySnapshot, payload.property_snapshot_id)
    if property_snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property snapshot not found")
    if property_snapshot.property_id != property_record.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Property snapshot does not belong to the specified property",
        )

    request = Request(
        public_id=_request_public_id(db),
        jurisdiction_id=payload.jurisdiction_id,
        requester_user_id=payload.requester_user_id,
        property_id=payload.property_id,
        property_snapshot_id=payload.property_snapshot_id,
        letter_type=payload.letter_type,
        processing_type=payload.processing_type,
        delivery_method=payload.delivery_method,
        status="draft",
        payment_status="unpaid",
        requester_first_name=payload.requester_first_name,
        requester_last_name=payload.requester_last_name,
        requester_email=str(payload.requester_email),
        requester_phone=payload.requester_phone,
        requester_organization=payload.requester_organization,
        mailing_address_json=payload.mailing_address_json,
        special_instructions=payload.special_instructions,
        total_amount_cents=0,
        currency="USD",
    )
    db.add(request)
    db.flush()

    db.add(
        RequestStatusEvent(
            request_id=request.id,
            from_status=None,
            to_status="draft",
            reason_code="created",
            reason_text="Request created",
            acted_by_user_id=request.requester_user_id,
        )
    )
    db.commit()
    db.refresh(request)
    return RequestRead.model_validate(request)


@router.get("", response_model=list[RequestRead])
def list_requests(
    requester_user_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[RequestRead]:
    stmt = select(Request)
    if requester_user_id:
        stmt = stmt.where(Request.requester_user_id == requester_user_id)
    if status_filter:
        stmt = stmt.where(Request.status == status_filter)
    requests = db.scalars(stmt.order_by(Request.created_at.desc())).all()
    return [RequestRead.model_validate(item) for item in requests]


@router.get("/{request_id}", response_model=RequestRead)
def get_request(request_id: str, db: Session = Depends(get_db)) -> RequestRead:
    request = _load_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return RequestRead.model_validate(request)


@router.get("/{request_id}/status-events", response_model=list[RequestStatusEventRead])
def list_request_status_events(request_id: str, db: Session = Depends(get_db)) -> list[RequestStatusEventRead]:
    request = _load_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    events = db.scalars(
        select(RequestStatusEvent)
        .where(RequestStatusEvent.request_id == request.id)
        .order_by(RequestStatusEvent.created_at.asc())
    ).all()
    return [RequestStatusEventRead.model_validate(item) for item in events]


@router.post("/{request_id}/submit", response_model=RequestRead)
def submit_request(
    request_id: str,
    payload: RequestSubmit,
    db: Session = Depends(get_db),
    auth: AuthContext | None = Depends(get_optional_auth_context),
) -> RequestRead:
    request = _load_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    actor = resolve_actor_user(db, explicit_user_id=payload.actor_user_id, auth=auth)
    if actor.id != request.requester_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the requester can submit this request",
        )

    try:
        ensure_transition_allowed(request.status, "submitted")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    request.status = "submitted"
    request.submitted_at = datetime.now(UTC).replace(tzinfo=None)
    db.add(
        RequestStatusEvent(
            request_id=request.id,
            from_status="draft",
            to_status="submitted",
            reason_code="submit_request",
            reason_text="Request submitted by requester",
            acted_by_user_id=actor.id,
        )
    )
    db.commit()
    db.refresh(request)
    try:
        send_request_status_email(db, request=request)
        db.commit()
    except Exception:
        db.rollback()
    return RequestRead.model_validate(request)


@router.post("/{request_id}/payment-received", response_model=RequestRead)
def confirm_request_payment(
    request_id: str,
    payload: RequestPaymentConfirm,
    db: Session = Depends(get_db),
    auth: AuthContext | None = Depends(get_optional_auth_context),
) -> RequestRead:
    request = _load_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    actor = resolve_actor_user(db, explicit_user_id=payload.actor_user_id, auth=auth)

    if request.status == "submitted":
        try:
            ensure_transition_allowed("submitted", "payment_pending")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        request.status = "payment_pending"
        db.add(
            RequestStatusEvent(
                request_id=request.id,
                from_status="submitted",
                to_status="payment_pending",
                reason_code="start_checkout",
                reason_text="Payment started",
                acted_by_user_id=actor.id,
            )
        )

    try:
        ensure_transition_allowed(request.status, "paid")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    previous_status = request.status
    request.status = "paid"
    request.payment_status = "paid"
    request.paid_at = datetime.now(UTC).replace(tzinfo=None)
    db.add(
        RequestStatusEvent(
            request_id=request.id,
            from_status=previous_status,
            to_status="paid",
            reason_code="confirm_payment",
            reason_text=payload.reason_text or "Payment confirmed",
            acted_by_user_id=actor.id,
        )
    )
    db.commit()
    db.refresh(request)
    try:
        send_request_status_email(db, request=request)
        db.commit()
    except Exception:
        db.rollback()
    return RequestRead.model_validate(request)


@router.post("/{request_id}/quote", response_model=QuoteRead)
def create_quote(
    request_id: str,
    db: Session = Depends(get_db),
) -> QuoteRead:
    request = _load_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    try:
        quote = build_quote_for_request(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.add(quote)
    db.flush()
    request.current_quote_id = quote.id
    request.total_amount_cents = quote.total_cents
    db.commit()
    db.refresh(quote)
    db.refresh(request)
    return QuoteRead.model_validate(quote)


@router.get("/{request_id}/quote", response_model=QuoteRead)
def get_current_quote(request_id: str, db: Session = Depends(get_db)) -> QuoteRead:
    request = _load_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if request.current_quote_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found")
    quote = db.get(Quote, request.current_quote_id)
    if quote is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found")
    return QuoteRead.model_validate(quote)


@router.post("/{request_id}/checkout", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def create_checkout(
    request_id: str,
    payload: PaymentCheckoutCreate,
    db: Session = Depends(get_db),
    auth: AuthContext | None = Depends(get_optional_auth_context),
) -> PaymentRead:
    request = _load_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    actor = resolve_actor_user(db, explicit_user_id=payload.actor_user_id, auth=auth)
    if request.current_quote_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request has no current quote")
    if request.status == "submitted":
        try:
            ensure_transition_allowed("submitted", "payment_pending")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        request.status = "payment_pending"
        db.add(
            RequestStatusEvent(
                request_id=request.id,
                from_status="submitted",
                to_status="payment_pending",
                reason_code="start_checkout",
                reason_text="Checkout created",
                acted_by_user_id=actor.id,
            )
        )
    payment = Payment(
        request_id=request.id,
        quote_id=request.current_quote_id,
        provider=payload.provider,
        amount_cents=request.total_amount_cents,
        currency=request.currency,
        receipt_url=f"/receipts/{request.public_id}",
    )
    try:
        checkout = get_payment_provider(payload.provider).create_checkout(
            request_public_id=request.public_id,
            amount_cents=request.total_amount_cents,
            currency=request.currency,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    payment.provider = checkout.provider
    payment.provider_checkout_id = checkout.external_id
    payment.status = checkout.status
    db.add(payment)
    db.commit()
    db.refresh(payment)
    try:
        send_request_status_email(db, request=request)
        db.commit()
    except Exception:
        db.rollback()
    return PaymentRead.model_validate(payment)
