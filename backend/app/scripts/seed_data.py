"""Seed local development data for UZone."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.models import (
    EmailTemplate,
    FeeSchedule,
    FeeScheduleItem,
    Jurisdiction,
    LetterTemplate,
    Property,
    PropertySnapshot,
    Request,
    RequestStatusEvent,
    Role,
    TenantClient,
    TenantDomain,
    User,
    UserRole,
)
from app.db.session import SessionLocal
from app.services.shared.auth_service import hash_password
from app.services.letters.email_template_service import ensure_default_email_templates

ADMIN_EMAIL = "admin@uzone.example.com"
STAFF_EMAIL = "staff@uzone.example.com"
CUSTOMER_EMAIL = "customer@uzone.example.com"
DREAMTOWN_EMAIL = "planning@dreamtown.gov"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _repair_seed_emails(db) -> None:
    email_repairs = {
        "admin@uzone.local": ADMIN_EMAIL,
        "staff@uzone.local": STAFF_EMAIL,
        "customer@uzone.local": CUSTOMER_EMAIL,
    }
    for old_email, new_email in email_repairs.items():
        user = db.scalar(select(User).where(User.email == old_email))
        if user is not None:
            user.email = new_email

    jurisdictions = db.scalars(
        select(Jurisdiction).where(Jurisdiction.public_contact_email == "planning@dreamtown.local")
    ).all()
    for jurisdiction in jurisdictions:
        jurisdiction.public_contact_email = DREAMTOWN_EMAIL

    tenants = db.scalars(
        select(TenantClient).where(TenantClient.support_email == "planning@dreamtown.local")
    ).all()
    for tenant in tenants:
        tenant.support_email = DREAMTOWN_EMAIL


def seed() -> None:
    db = SessionLocal()
    try:
        _repair_seed_emails(db)
        existing_jurisdiction = db.scalar(select(Jurisdiction).limit(1))
        if existing_jurisdiction is not None:
            existing_tenant = db.scalar(select(TenantClient).limit(1))
            if existing_tenant is None:
                tenant_client = TenantClient(
                    client_id=existing_jurisdiction.code,
                    jurisdiction_id=existing_jurisdiction.id,
                    city_name=existing_jurisdiction.name,
                    department_name=existing_jurisdiction.department_name,
                    standard_letter_fee_cents=7500,
                    comprehensive_letter_fee_cents=15000,
                    expedited_fee_cents=5000,
                    support_phone="(555) 123-4567",
                    support_email=existing_jurisdiction.public_contact_email or DREAMTOWN_EMAIL,
                    contact_address="123 City Hall Plaza",
                )
                db.add(tenant_client)
                db.flush()
                db.add_all(
                    [
                        TenantDomain(
                            tenant_client_id=tenant_client.id,
                            hostname="localhost",
                            is_primary=True,
                        ),
                        TenantDomain(
                            tenant_client_id=tenant_client.id,
                            hostname="127.0.0.1",
                            is_primary=False,
                        ),
                    ]
                )
                db.commit()
            else:
                db.commit()
            return

        admin = User(
            email=ADMIN_EMAIL,
            password_hash=hash_password("password123"),
            first_name="Admin",
            last_name="User",
            organization="UZone",
        )
        processor = User(
            email=STAFF_EMAIL,
            password_hash=hash_password("password123"),
            first_name="Staff",
            last_name="Processor",
            organization="UZone",
        )
        customer = User(
            email=CUSTOMER_EMAIL,
            password_hash=hash_password("password123"),
            first_name="Casey",
            last_name="Requester",
            organization="Acme Development",
        )
        db.add_all([admin, processor, customer])
        db.flush()

        admin_role = Role(code="admin", name="Administrator", description="Full admin access")
        processor_role = Role(
            code="request_processor",
            name="Request Processor",
            description="Can process requests",
        )
        public_role = Role(code="public_user", name="Public User", description="Can submit requests")
        db.add_all([admin_role, processor_role, public_role])
        db.flush()

        db.add_all(
            [
                UserRole(user_id=admin.id, role_id=admin_role.id, granted_by_user_id=admin.id),
                UserRole(user_id=processor.id, role_id=processor_role.id, granted_by_user_id=admin.id),
                UserRole(user_id=customer.id, role_id=public_role.id, granted_by_user_id=admin.id),
            ]
        )

        jurisdiction = Jurisdiction(
            code="dream-town",
            name="City of Dream Town",
            department_name="Planning & Zoning Department",
            public_site_title="Dream Town Zoning Verification",
            public_contact_email=DREAMTOWN_EMAIL,
            public_contact_phone="555-0100",
            timezone="UTC",
        )
        db.add(jurisdiction)
        db.flush()

        tenant_client = TenantClient(
            client_id="dream-town",
            jurisdiction_id=jurisdiction.id,
            city_name="City of Dream Town",
            department_name="Planning & Zoning Department",
            standard_letter_fee_cents=7500,
            comprehensive_letter_fee_cents=15000,
            expedited_fee_cents=5000,
            support_phone="(555) 123-4567",
            support_email=DREAMTOWN_EMAIL,
            contact_address="123 City Hall Plaza",
        )
        db.add(tenant_client)
        db.flush()
        db.add_all(
            [
                TenantDomain(tenant_client_id=tenant_client.id, hostname="localhost", is_primary=True),
                TenantDomain(tenant_client_id=tenant_client.id, hostname="127.0.0.1", is_primary=False),
            ]
        )

        property_record = Property(
            jurisdiction_id=jurisdiction.id,
            source_system="manual",
            source_property_id="demo-123",
            group_id="grp-123",
            apn="123-456-789",
            address_line1="1234 Main Street",
            city="Dream Town",
            state="CA",
            postal_code="90210",
        )
        db.add(property_record)
        db.flush()

        snapshot = PropertySnapshot(
            property_id=property_record.id,
            captured_by_user_id=admin.id,
            capture_reason="request_submission",
            address="1234 Main Street, Dream Town, CA 90210",
            apn="123-456-789",
            group_id="grp-123",
            zoning_code="R-1",
            zoning_name="Single Family Residential",
            lot_size_sf=10890,
            permitted_uses_json=["Single-family dwellings", "ADUs", "Home occupations"],
            restrictions_json={"height_ft": 35},
            overlays_json=[],
            raw_source_payload_json={"demo": True},
            source_payload_hash="seed-demo",
        )
        db.add(snapshot)
        db.flush()

        schedule = FeeSchedule(
            jurisdiction_id=jurisdiction.id,
            name="Default 2026 Fees",
            status="active",
            effective_start_at=_utcnow() - timedelta(days=1),
            created_by_user_id=admin.id,
        )
        db.add(schedule)
        db.flush()

        db.add_all(
            [
                FeeScheduleItem(
                    fee_schedule_id=schedule.id,
                    code="standard_letter",
                    name="Standard Letter",
                    fee_type="base",
                    amount_cents=7500,
                    applies_to_letter_type="standard",
                    currency="USD",
                ),
                FeeScheduleItem(
                    fee_schedule_id=schedule.id,
                    code="comprehensive_letter",
                    name="Comprehensive Letter",
                    fee_type="base",
                    amount_cents=15000,
                    applies_to_letter_type="comprehensive",
                    currency="USD",
                ),
                FeeScheduleItem(
                    fee_schedule_id=schedule.id,
                    code="rush_processing",
                    name="Rush Processing",
                    fee_type="addon",
                    amount_cents=5000,
                    applies_to_processing_type="expedited",
                    currency="USD",
                ),
                FeeScheduleItem(
                    fee_schedule_id=schedule.id,
                    code="mail_delivery",
                    name="Physical Mail Delivery",
                    fee_type="addon",
                    amount_cents=1500,
                    applies_to_delivery_method="mail",
                    currency="USD",
                ),
            ]
        )

        standard_template = LetterTemplate(
            jurisdiction_id=jurisdiction.id,
            code="standard-default",
            name="Standard Letter Template",
            letter_type="standard",
            status="active",
            template_body=(
                "<h1>Zoning Verification Letter</h1>"
                "<p>Request {{request_id}}</p>"
                "<p>Requester: {{requester_name}}</p>"
                "<p>Property: {{property_address}}</p>"
                "<p>APN: {{apn}}</p>"
                "<p>Zoning: {{zoning_code}} {{zoning_name}}</p>"
            ),
            merge_variables_json=[
                "request_id",
                "requester_name",
                "property_address",
                "apn",
                "zoning_code",
                "zoning_name",
            ],
            version=1,
            created_by_user_id=admin.id,
        )
        comprehensive_template = LetterTemplate(
            jurisdiction_id=jurisdiction.id,
            code="comprehensive-default",
            name="Comprehensive Letter Template",
            letter_type="comprehensive",
            status="active",
            template_body=(
                "<h1>Comprehensive Zoning Verification Letter</h1>"
                "<p>Request {{request_id}}</p>"
                "<p>Requester: {{requester_name}}</p>"
                "<p>Property: {{property_address}}</p>"
                "<p>APN: {{apn}}</p>"
                "<p>Zoning: {{zoning_code}} {{zoning_name}}</p>"
                "<p>Letter type: {{letter_type}}</p>"
            ),
            merge_variables_json=[
                "request_id",
                "requester_name",
                "property_address",
                "apn",
                "zoning_code",
                "zoning_name",
                "letter_type",
            ],
            version=1,
            created_by_user_id=admin.id,
        )
        db.add_all([standard_template, comprehensive_template])
        db.flush()
        ensure_default_email_templates(db)
        submitted_default = db.scalar(
            select(EmailTemplate).where(
                EmailTemplate.is_system_default.is_(True),
                EmailTemplate.code == "submitted",
            )
        )
        if submitted_default is not None:
            db.add(
                EmailTemplate(
                    jurisdiction_id=jurisdiction.id,
                    tenant_client_id=tenant_client.id,
                    owner_organization_id=tenant_client.clerk_organization_id or tenant_client.client_id,
                    base_template_id=submitted_default.id,
                    code=submitted_default.code,
                    trigger_state=submitted_default.trigger_state,
                    name="Request Submitted",
                    description="Dream Town override for the initial submission notice.",
                    category="request_updates",
                    subject_template="City of Dream Town received request {{request_id}}",
                    body_template=(
                        "<p>Hello {{requester_name}},</p>"
                        "<p>The City of Dream Town received request {{request_id}} for {{property_address}}.</p>"
                        "<p>We will email you again when review begins.</p>"
                    ),
                    status="active",
                    version=1,
                    created_by_user_id=admin.id,
                    is_system_default=False,
                )
            )

        sample_request = Request(
            public_id="ZVL-2026-000001",
            jurisdiction_id=jurisdiction.id,
            requester_user_id=customer.id,
            property_id=property_record.id,
            property_snapshot_id=snapshot.id,
            letter_type="comprehensive",
            processing_type="expedited",
            delivery_method="email",
            status="submitted",
            payment_status="unpaid",
            requester_first_name=customer.first_name,
            requester_last_name=customer.last_name,
            requester_email=customer.email,
            requester_phone=customer.phone,
            requester_organization=customer.organization,
            total_amount_cents=0,
            currency="USD",
            submitted_at=_utcnow(),
        )
        db.add(sample_request)
        db.flush()
        db.add_all(
            [
                RequestStatusEvent(
                    request_id=sample_request.id,
                    from_status=None,
                    to_status="draft",
                    reason_code="created",
                    reason_text="Seeded request created",
                    acted_by_user_id=customer.id,
                ),
                RequestStatusEvent(
                    request_id=sample_request.id,
                    from_status="draft",
                    to_status="submitted",
                    reason_code="submit_request",
                    reason_text="Seeded request submitted",
                    acted_by_user_id=customer.id,
                ),
            ]
        )

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
