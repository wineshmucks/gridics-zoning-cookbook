"""Route coverage for requests, staff requests, and payments."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select

from app.api.v1 import payments, requests, staff_requests
from app.core.security import AuthContext
from app.db.models import LetterDraft, LetterTemplate, LetterVersion, Payment, PaymentEvent, Quote
from app.schemas import (
    ApprovalAction,
    DeliveryAction,
    LetterDraftCreate,
    PaymentCheckoutCreate,
    RequestAssign,
    RequestCreate,
    RequestNoteCreate,
    RequestPaymentConfirm,
    RequestStartReview,
    RequestSubmit,
)
from .helpers import add_jurisdiction, add_property, add_property_snapshot, add_request, add_user, make_db


def test_request_routes_cover_create_list_get_and_events() -> None:
    db = make_db()
    try:
        add_jurisdiction(db)
        requester = add_user(db, id="user-requester", email="requester@example.com")
        property_record = add_property(db)
        snapshot = add_property_snapshot(db)

        created = requests.create_request(
            RequestCreate(
                jurisdiction_id="jur-1",
                requester_user_id=requester.id,
                property_id=property_record.id,
                property_snapshot_id=snapshot.id,
                letter_type="standard",
                processing_type="standard",
                delivery_method="email",
                requester_first_name="Ada",
                requester_last_name="Lovelace",
                requester_email="ada@example.com",
            ),
            db=db,
        )
        assert created.status == "draft"

        listed = requests.list_requests(requester_user_id=requester.id, status_filter=None, db=db)
        assert [item.id for item in listed] == [created.id]
        assert requests.get_request(created.id, db=db).id == created.id
        assert len(requests.list_request_status_events(created.id, db=db)) == 1

        second = requests.create_request(
            RequestCreate(
                jurisdiction_id="jur-1",
                requester_user_id=requester.id,
                property_id=property_record.id,
                property_snapshot_id=snapshot.id,
                letter_type="standard",
                processing_type="standard",
                delivery_method="email",
                requester_first_name="Ada",
                requester_last_name="Lovelace",
                requester_email="ada@example.com",
            ),
            db=db,
        )
        assert second.id != created.id
    finally:
        db.close()


def test_request_routes_reject_bad_property_and_snapshot_relationships() -> None:
    db = make_db()
    try:
        add_jurisdiction(db)
        add_jurisdiction(db, id="jur-2", code="other-town", name="Other Town")
        add_user(db)
        property_record = add_property(db, jurisdiction_id="jur-2")
        snapshot = add_property_snapshot(db, property_id=property_record.id)

        try:
            requests.create_request(
                RequestCreate(
                    jurisdiction_id="jur-1",
                    requester_user_id="user-1",
                    property_id=property_record.id,
                    property_snapshot_id=snapshot.id,
                    letter_type="standard",
                    processing_type="standard",
                    delivery_method="email",
                    requester_first_name="Ada",
                    requester_last_name="Lovelace",
                    requester_email="ada@example.com",
                ),
                db=db,
            )
        except HTTPException as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("Requests must reject properties outside the jurisdiction.")
    finally:
        db.close()


def test_submit_request_confirm_payment_and_checkout(monkeypatch) -> None:
    db = make_db()
    try:
        add_jurisdiction(db)
        requester = add_user(db, id="requester-1", email="requester@example.com")
        staff = add_user(db, id="staff-1", email="staff@example.com")
        add_property(db)
        add_property_snapshot(db)
        request = add_request(db, requester_user_id=requester.id)
        quote = Quote(
            id="quote-1",
            request_id=request.id,
            fee_schedule_id="schedule-1",
            status="generated",
            line_items_json=[{"code": "base", "name": "Base", "amount_cents": 5000, "currency": "USD"}],
            subtotal_cents=5000,
            tax_cents=0,
            total_cents=5000,
            currency="USD",
        )
        db.add(quote)
        db.commit()
        request.current_quote_id = quote.id
        request.total_amount_cents = 5000
        db.commit()

        monkeypatch.setattr(requests, "send_request_status_email", lambda *args, **kwargs: None)
        monkeypatch.setattr(requests, "build_quote_for_request", lambda db_session, req: quote)

        submitted = requests.submit_request(
            request.id,
            RequestSubmit(actor_user_id=requester.id),
            db=db,
            auth=None,
        )
        assert submitted.status == "submitted"
        assert submitted.submitted_at is not None

        try:
            requests.submit_request(
                request.id,
                RequestSubmit(actor_user_id=staff.id),
                db=db,
                auth=None,
            )
        except HTTPException as exc:
            assert exc.status_code == 403
        else:
            raise AssertionError("Only the requester should be able to submit.")

        payment_pending = requests.confirm_request_payment(
            request.id,
            RequestPaymentConfirm(actor_user_id=requester.id, reason_text="Paid at counter"),
            db=db,
            auth=None,
        )
        assert payment_pending.status == "paid"
        assert payment_pending.payment_status == "paid"

        class FakeProvider:
            def create_checkout(self, *, request_public_id: str, amount_cents: int, currency: str):
                return SimpleNamespace(provider="manual", external_id="checkout-1", status="pending")

        monkeypatch.setattr(requests, "get_payment_provider", lambda provider: FakeProvider())
        checkout = requests.create_checkout(
            request.id,
            PaymentCheckoutCreate(actor_user_id=requester.id, provider="manual"),
            db=db,
            auth=None,
        )
        assert checkout.provider_checkout_id == "checkout-1"

        request.current_quote_id = None
        db.commit()
        try:
            requests.create_checkout(
                request.id,
                PaymentCheckoutCreate(actor_user_id=requester.id, provider="manual"),
                db=db,
                auth=None,
            )
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("Checkout should require a current quote.")
    finally:
        db.close()


def test_submit_request_rejects_invalid_transition(monkeypatch) -> None:
    db = make_db()
    try:
        add_jurisdiction(db)
        requester = add_user(db, id="requester-1", email="requester@example.com")
        add_property(db)
        add_property_snapshot(db)
        request = add_request(db, requester_user_id=requester.id)

        monkeypatch.setattr(requests, "send_request_status_email", lambda *args, **kwargs: None)
        request.status = "approved"
        db.commit()
        try:
            requests.submit_request(request.id, RequestSubmit(actor_user_id=requester.id), db=db, auth=None)
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("Invalid request transitions should be rejected.")
    finally:
        db.close()


def test_staff_request_routes_cover_queue_assign_review_notes_draft_approve_and_deliver(monkeypatch) -> None:
    db = make_db()
    try:
        add_jurisdiction(db)
        requester = add_user(db, id="requester-1", email="requester@example.com")
        assignee = add_user(db, id="staff-1", email="staff@example.com")
        other_staff = add_user(db, id="staff-2", email="other@example.com")
        add_property(db)
        add_property_snapshot(db)
        request = add_request(db, requester_user_id=requester.id, status="paid", payment_status="paid")
        template = LetterTemplate(
            id="template-1",
            jurisdiction_id="jur-1",
            code="standard-letter",
            name="Standard Letter",
            letter_type="standard",
            status="active",
            template_body="Hello {{ requester_first_name }}",
            merge_variables_json={},
            version=1,
            created_by_user_id=requester.id,
        )
        db.add(template)
        db.commit()

        monkeypatch.setattr(staff_requests, "send_request_status_email", lambda *args, **kwargs: None)
        monkeypatch.setattr(
            staff_requests,
            "build_draft",
            lambda db_session, req, actor_user_id: LetterDraft(
                id="draft-1",
                request_id=req.id,
                template_id=template.id,
                status="generated",
                generated_body="Draft body",
                editable_sections_json={},
                generated_from_snapshot_id=req.property_snapshot_id,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            ),
        )
        monkeypatch.setattr(
            staff_requests,
            "build_letter_version",
            lambda req, draft, version_type, actor_user_id: LetterVersion(
                id="version-1",
                request_id=req.id,
                draft_id=draft.id,
                version_number=1,
                version_type=version_type,
                html_body="<p>Signed</p>",
                signed_by_user_id=actor_user_id,
            ),
        )
        monkeypatch.setattr(staff_requests, "generate_pdf_for_version", lambda version: "/tmp/version-1.pdf")

        listed = staff_requests.list_staff_requests(status_filter=None, assigned_to_user_id=None, jurisdiction_id=None, db=db)
        assert listed
        assert staff_requests.get_staff_request(request.id, db=db).id == request.id
        assert staff_requests.get_staff_request_status_events(request.id, db=db) == []

        assigned = staff_requests.assign_staff_request(
            request.id,
            RequestAssign(assigned_to_user_id=assignee.id, assigned_by_user_id=assignee.id, assignment_reason="Queue"),
            db=db,
            auth=None,
        )
        assert assigned.status == "pending_review"
        assert assigned.assigned_to_user_id == assignee.id

        review_started = staff_requests.start_staff_review(
            request.id,
            RequestStartReview(actor_user_id=assignee.id, reason_text="Starting review"),
            db=db,
            auth=None,
        )
        assert review_started.status == "in_progress"

        note = staff_requests.create_staff_request_note(
            request.id,
            RequestNoteCreate(author_user_id=assignee.id, note_type="internal", visibility="staff_only", body="Looks good."),
            db=db,
            auth=None,
        )
        assert note.body == "Looks good."

        draft = staff_requests.create_staff_request_draft(
            request.id,
            LetterDraftCreate(actor_user_id=assignee.id),
            db=db,
            auth=None,
        )
        assert draft.request_id == request.id

        approved = staff_requests.approve_staff_request(
            request.id,
            ApprovalAction(actor_user_id=assignee.id, reason_text="Approved"),
            db=db,
            auth=None,
        )
        assert approved.status == "approved"
        assert approved.final_letter_version_id is not None

        delivered = staff_requests.deliver_staff_request(
            request.id,
            DeliveryAction(actor_user_id=assignee.id, destination="100 Main Street", provider_reference="tracking-1"),
            db=db,
            auth=None,
        )
        assert delivered.status == "delivered"

        request2 = add_request(db, id="req-2", public_id="ZVL-2026-000002", requester_user_id=requester.id, status="in_progress", payment_status="paid")
        request2.current_draft_id = draft.id
        db.commit()
        monkeypatch.setattr(
            staff_requests,
            "ensure_transition_allowed",
            lambda from_status, to_status: (_ for _ in ()).throw(ValueError("blocked"))
            if (from_status, to_status) == ("in_progress", "awaiting_final_signature")
            else None,
        )
        try:
            staff_requests.approve_staff_request(
                request2.id,
                ApprovalAction(actor_user_id=assignee.id),
                db=db,
                auth=None,
            )
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("Invalid approval transitions should be translated into 409 responses.")

        try:
            staff_requests.start_staff_review(
                request.id,
                RequestStartReview(actor_user_id=other_staff.id),
                db=db,
                auth=None,
            )
        except HTTPException as exc:
            assert exc.status_code == 403
        else:
            raise AssertionError("Review assignment should enforce current assignee ownership.")
    finally:
        db.close()


def test_payment_webhook_updates_payment_and_request(monkeypatch) -> None:
    db = make_db()
    try:
        add_jurisdiction(db)
        requester = add_user(db, id="requester-1", email="requester@example.com")
        add_property(db)
        add_property_snapshot(db)
        request = add_request(db, requester_user_id=requester.id, status="payment_pending", payment_status="unpaid")
        payment = Payment(
            id="payment-1",
            request_id=request.id,
            quote_id="quote-1",
            provider="stripe",
            provider_checkout_id="pi_123",
            status="pending",
            amount_cents=5000,
            currency="USD",
            receipt_url="/receipts/ZVL-2026-000001",
        )
        db.add(payment)
        db.commit()
        monkeypatch.setattr(payments, "send_request_status_email", lambda *args, **kwargs: None)
        monkeypatch.setattr(
            payments,
            "verify_stripe_webhook",
            lambda payload, signature: {
                "id": "evt-1",
                "type": "payment_intent.succeeded",
                "data": {"object": {"id": "pi_123"}},
            },
        )

        class FakeRequest:
            async def body(self):
                return b"{}"

        result = asyncio.run(
            payments.stripe_webhook(
                request=FakeRequest(),
                db=db,
                stripe_signature="sig",
            )
        )
        assert result["status"] == "processed"
        db.refresh(payment)
        db.refresh(request)
        assert payment.status == "paid"
        assert request.status == "paid"
        assert db.scalar(select(PaymentEvent).where(PaymentEvent.payment_id == payment.id)) is not None

        monkeypatch.setattr(
            payments,
            "verify_stripe_webhook",
            lambda payload, signature: (_ for _ in ()).throw(ValueError("bad signature")),
        )
        try:
            asyncio.run(payments.stripe_webhook(request=FakeRequest(), db=db, stripe_signature="sig"))
        except HTTPException as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("Invalid webhook signatures should be rejected.")
    finally:
        db.close()
