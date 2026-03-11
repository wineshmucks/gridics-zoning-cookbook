"""Unit tests for request status email delivery."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import EmailTemplate, Jurisdiction, PropertySnapshot, Request, TenantClient
from app.services.email_service import send_request_status_email
from app.services.email_template_service import ensure_default_email_templates


class DummyProvider:
    name = "dummy"

    def send(self, *, to: str, subject: str, html: str, text: str | None = None):
        class Result:
            provider = "dummy"
            provider_message_id = "msg-1"
            status = "sent"

        return Result()


def _db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_local()


def test_send_request_status_email_uses_customer_override(monkeypatch) -> None:
    from app.services import email_service

    monkeypatch.setattr(email_service, "get_email_provider", lambda: DummyProvider())

    db = _db()
    try:
        jurisdiction = Jurisdiction(
            code="tenant-c",
            name="Tenant C",
            department_name="Planning & Zoning Department",
            timezone="UTC",
        )
        db.add(jurisdiction)
        db.flush()
        tenant = TenantClient(
            client_id="tenant-c",
            jurisdiction_id=jurisdiction.id,
            city_name="Tenant C",
            department_name="Planning & Zoning Department",
            standard_letter_fee_cents=7500,
            comprehensive_letter_fee_cents=15000,
            expedited_fee_cents=5000,
        )
        db.add(tenant)
        db.flush()
        snapshot = PropertySnapshot(
            id="snap-1",
            property_id="prop-1",
            captured_by_user_id=None,
            capture_reason="request_submission",
            address="100 Main Street",
            apn="123-456",
            group_id="grp-1",
            zoning_code="R-1",
            zoning_name="Residential",
            lot_size_sf=5000,
            permitted_uses_json=[],
            restrictions_json={},
            overlays_json=[],
            raw_source_payload_json={},
            source_payload_hash="hash-1",
        )
        db.add(snapshot)
        request = Request(
            id="req-1",
            public_id="ZVL-2026-000001",
            jurisdiction_id=jurisdiction.id,
            requester_user_id="user-1",
            property_id="prop-1",
            property_snapshot_id=snapshot.id,
            letter_type="standard",
            processing_type="standard",
            delivery_method="email",
            status="approved",
            payment_status="paid",
            requester_first_name="Taylor",
            requester_last_name="Jones",
            requester_email="taylor@example.com",
            total_amount_cents=7500,
            currency="USD",
        )
        db.add(request)
        db.commit()

        ensure_default_email_templates(db)
        default_template = db.query(EmailTemplate).filter_by(code="approved", is_system_default=True).one()
        override = EmailTemplate(
            jurisdiction_id=jurisdiction.id,
            tenant_client_id=tenant.id,
            owner_organization_id=tenant.client_id,
            base_template_id=default_template.id,
            code="approved",
            trigger_state="approved",
            name="Approved Override",
            description="Customer approval email.",
            category="request_updates",
            subject_template="Tenant C approved {{request_id}}",
            body_template="<p>Hello {{requester_name}}, approved for {{property_address}}.</p>",
            status="active",
            version=1,
            created_by_user_id=None,
            is_system_default=False,
        )
        db.add(override)
        db.commit()

        event = send_request_status_email(db, request=request)
        db.commit()

        assert event is not None
        assert event.template_id == override.id
        assert event.subject_rendered == "Tenant C approved ZVL-2026-000001"
        assert "100 Main Street" in event.body_rendered
    finally:
        db.close()
