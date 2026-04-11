"""Staff request routes."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_optional_auth_context, resolve_actor_user
from app.core.security import AuthContext
from app.domain.request_states import ensure_transition_allowed
from app.db.models import (
    Delivery,
    LetterDraft,
    Request,
    RequestAssignment,
    RequestNote,
    RequestStatusEvent,
    User,
)
from app.schemas import (
    ApprovalAction,
    DeliveryAction,
    DeliveryRead,
    LetterDraftCreate,
    LetterDraftRead,
    RequestAssign,
    RequestNoteCreate,
    RequestNoteRead,
    RequestRead,
    RequestStartReview,
    RequestStatusEventRead,
)
from app.services.document_service import build_draft, build_letter_version
from app.services.document_service import generate_pdf_for_version
from app.services.email_service import send_request_status_email

router = APIRouter()


def _load_request(db: Session, request_id: str) -> Request | None:
    request = db.get(Request, request_id)
    if request is None:
        request = db.scalar(select(Request).where(Request.public_id == request_id))
    return request


@router.get("", response_model=list[RequestRead])
def list_staff_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    assigned_to_user_id: str | None = None,
    jurisdiction_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[RequestRead]:
    stmt = select(Request)
    if status_filter:
        stmt = stmt.where(Request.status == status_filter)
    if assigned_to_user_id:
        stmt = stmt.where(Request.assigned_to_user_id == assigned_to_user_id)
    if jurisdiction_id:
        stmt = stmt.where(Request.jurisdiction_id == jurisdiction_id)
    requests = db.scalars(stmt.order_by(Request.created_at.desc())).all()
    return [RequestRead.model_validate(item) for item in requests]


@router.get("/{request_id}", response_model=RequestRead)
def get_staff_request(request_id: str, db: Session = Depends(get_db)) -> RequestRead:
    request = _load_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return RequestRead.model_validate(request)


@router.get("/{request_id}/status-events", response_model=list[RequestStatusEventRead])
def get_staff_request_status_events(
    request_id: str,
    db: Session = Depends(get_db),
) -> list[RequestStatusEventRead]:
    request = _load_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    events = db.scalars(
        select(RequestStatusEvent)
        .where(RequestStatusEvent.request_id == request.id)
        .order_by(RequestStatusEvent.created_at.asc())
    ).all()
    return [RequestStatusEventRead.model_validate(item) for item in events]


@router.post("/{request_id}/assign", response_model=RequestRead)
def assign_staff_request(
    request_id: str,
    payload: RequestAssign,
    db: Session = Depends(get_db),
    auth: AuthContext | None = Depends(get_optional_auth_context),
) -> RequestRead:
    request = _load_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")

    assignee = db.get(User, payload.assigned_to_user_id)
    if assignee is None:
        raise HTTPException(status_code=404, detail="Assigned user not found")
    assigner = resolve_actor_user(
        db,
        explicit_user_id=payload.assigned_by_user_id or payload.assigned_to_user_id,
        auth=auth,
    )

    if request.status == "paid":
        try:
            ensure_transition_allowed("paid", "pending_review")
            request.status = "pending_review"
            db.add(
                RequestStatusEvent(
                    request_id=request.id,
                    from_status="paid",
                    to_status="pending_review",
                    reason_code="queue_request",
                    reason_text="Request entered staff queue",
                    acted_by_user_id=assigner.id,
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    current_assignment = None
    if request.assigned_to_user_id:
        current_assignment = db.scalar(
            select(RequestAssignment)
            .where(
                RequestAssignment.request_id == request.id,
                RequestAssignment.ended_at.is_(None),
            )
            .order_by(RequestAssignment.created_at.desc())
        )
    if current_assignment is not None:
        current_assignment.ended_at = datetime.now(UTC).replace(tzinfo=None)

    request.assigned_to_user_id = assignee.id
    db.add(
        RequestAssignment(
            request_id=request.id,
            assigned_to_user_id=assignee.id,
            assigned_by_user_id=assigner.id,
            assignment_reason=payload.assignment_reason,
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


@router.post("/{request_id}/start-review", response_model=RequestRead)
def start_staff_review(
    request_id: str,
    payload: RequestStartReview,
    db: Session = Depends(get_db),
    auth: AuthContext | None = Depends(get_optional_auth_context),
) -> RequestRead:
    request = _load_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")

    actor = resolve_actor_user(db, explicit_user_id=payload.actor_user_id, auth=auth)

    if request.assigned_to_user_id and request.assigned_to_user_id != actor.id:
        raise HTTPException(status_code=403, detail="Request is assigned to a different user")

    if request.status == "paid":
        try:
            ensure_transition_allowed("paid", "pending_review")
            request.status = "pending_review"
            db.add(
                RequestStatusEvent(
                    request_id=request.id,
                    from_status="paid",
                    to_status="pending_review",
                    reason_code="queue_request",
                    reason_text="Request entered staff queue",
                    acted_by_user_id=actor.id,
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        ensure_transition_allowed(request.status, "in_progress")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    previous_status = request.status
    request.status = "in_progress"
    if request.assigned_to_user_id is None:
        request.assigned_to_user_id = actor.id
        db.add(
            RequestAssignment(
                request_id=request.id,
                assigned_to_user_id=actor.id,
                assigned_by_user_id=actor.id,
                assignment_reason="Auto-assigned on review start",
            )
        )
    db.add(
        RequestStatusEvent(
            request_id=request.id,
            from_status=previous_status,
            to_status="in_progress",
            reason_code="start_review",
            reason_text=payload.reason_text or "Staff review started",
            acted_by_user_id=actor.id,
        )
    )
    db.commit()
    db.refresh(request)
    return RequestRead.model_validate(request)


@router.get("/{request_id}/notes", response_model=list[RequestNoteRead])
def list_staff_request_notes(
    request_id: str,
    db: Session = Depends(get_db),
) -> list[RequestNoteRead]:
    request = _load_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    notes = db.scalars(
        select(RequestNote)
        .where(RequestNote.request_id == request.id)
        .order_by(RequestNote.created_at.asc())
    ).all()
    return [RequestNoteRead.model_validate(item) for item in notes]


@router.post("/{request_id}/notes", response_model=RequestNoteRead)
def create_staff_request_note(
    request_id: str,
    payload: RequestNoteCreate,
    db: Session = Depends(get_db),
    auth: AuthContext | None = Depends(get_optional_auth_context),
) -> RequestNoteRead:
    request = _load_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")

    author = resolve_actor_user(db, explicit_user_id=payload.author_user_id, auth=auth)

    note = RequestNote(
        request_id=request.id,
        author_user_id=author.id,
        note_type=payload.note_type,
        visibility=payload.visibility,
        body=payload.body,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return RequestNoteRead.model_validate(note)


@router.post("/{request_id}/drafts", response_model=LetterDraftRead, status_code=201)
def create_staff_request_draft(
    request_id: str,
    payload: LetterDraftCreate,
    db: Session = Depends(get_db),
    auth: AuthContext | None = Depends(get_optional_auth_context),
) -> LetterDraftRead:
    request = _load_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    actor = resolve_actor_user(db, explicit_user_id=payload.actor_user_id, auth=auth)
    try:
        draft = build_draft(db, request, actor.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.add(draft)
    db.flush()
    request.current_draft_id = draft.id
    db.commit()
    db.refresh(draft)
    return LetterDraftRead.model_validate(draft)


@router.post("/{request_id}/approve", response_model=RequestRead)
def approve_staff_request(
    request_id: str,
    payload: ApprovalAction,
    db: Session = Depends(get_db),
    auth: AuthContext | None = Depends(get_optional_auth_context),
) -> RequestRead:
    request = _load_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    actor = resolve_actor_user(db, explicit_user_id=payload.actor_user_id, auth=auth)
    if request.current_draft_id is None:
        raise HTTPException(status_code=409, detail="Request has no current draft")
    draft = db.get(LetterDraft, request.current_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    if request.status == "in_progress":
        ensure_transition_allowed("in_progress", "awaiting_final_signature")
        request.status = "awaiting_final_signature"
        db.add(
            RequestStatusEvent(
                request_id=request.id,
                from_status="in_progress",
                to_status="awaiting_final_signature",
                reason_code="send_to_signer",
                reason_text="Draft ready for approval",
                acted_by_user_id=actor.id,
            )
        )
    try:
        ensure_transition_allowed(request.status, "approved")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    version = build_letter_version(request, draft, "signed_pdf", actor.id)
    db.add(version)
    db.flush()
    version.pdf_storage_key = generate_pdf_for_version(version)
    previous_status = request.status
    request.status = "approved"
    request.approved_at = datetime.now(UTC).replace(tzinfo=None)
    request.final_letter_version_id = version.id
    db.add(
        RequestStatusEvent(
            request_id=request.id,
            from_status=previous_status,
            to_status="approved",
            reason_code="approve_request",
            reason_text=payload.reason_text or "Request approved",
            acted_by_user_id=actor.id,
        )
    )
    db.commit()
    db.refresh(request)
    return RequestRead.model_validate(request)


@router.post("/{request_id}/deliver", response_model=DeliveryRead, status_code=201)
def deliver_staff_request(
    request_id: str,
    payload: DeliveryAction,
    db: Session = Depends(get_db),
    auth: AuthContext | None = Depends(get_optional_auth_context),
) -> DeliveryRead:
    request = _load_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    actor = resolve_actor_user(db, explicit_user_id=payload.actor_user_id, auth=auth)
    if request.final_letter_version_id is None:
        raise HTTPException(status_code=409, detail="Request has no final letter version")
    try:
        ensure_transition_allowed(request.status, "delivered")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    delivery = Delivery(
        request_id=request.id,
        letter_version_id=request.final_letter_version_id,
        delivery_method=request.delivery_method,
        status="delivered",
        destination=payload.destination,
        provider_reference=payload.provider_reference,
        delivered_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(delivery)
    previous_status = request.status
    request.status = "delivered"
    request.delivered_at = delivery.delivered_at
    db.add(
        RequestStatusEvent(
            request_id=request.id,
            from_status=previous_status,
            to_status="delivered",
            reason_code="deliver_request",
            reason_text="Request delivered",
            acted_by_user_id=actor.id,
        )
    )
    db.commit()
    db.refresh(delivery)
    try:
        send_request_status_email(
            db,
            request=request,
            extra_variables={
                "delivery_destination": payload.destination,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
    return DeliveryRead.model_validate(delivery)
