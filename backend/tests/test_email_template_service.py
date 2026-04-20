"""Unit tests for email template defaults and customer overrides."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import EmailTemplate, Jurisdiction, TenantClient
from app.services.email_template_service import (
    ensure_default_email_templates,
    get_active_email_template_for_client,
    get_effective_email_templates,
)


def _db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_local()


def test_effective_templates_fall_back_to_gridics_defaults() -> None:
    db = _db()
    try:
        jurisdiction = Jurisdiction(
            code="tenant-a",
            name="Tenant A",
            department_name="Planning & Zoning Department",
            timezone="UTC",
        )
        db.add(jurisdiction)
        db.flush()
        tenant = TenantClient(
            client_id="tenant-a",
            jurisdiction_id=jurisdiction.id,
            city_name="Tenant A",
            department_name="Planning & Zoning Department",
            standard_letter_fee_cents=7500,
            comprehensive_letter_fee_cents=15000,
            expedited_fee_cents=5000,
        )
        db.add(tenant)
        db.commit()

        templates = get_effective_email_templates(db, tenant)

        assert templates
        assert all(item.default_template.is_system_default for item in templates)
        assert all(item.override_template is None for item in templates)
    finally:
        db.close()


def test_customer_override_replaces_default_for_matching_code() -> None:
    db = _db()
    try:
        jurisdiction = Jurisdiction(
            code="tenant-b",
            name="Tenant B",
            department_name="Planning & Zoning Department",
            timezone="UTC",
        )
        db.add(jurisdiction)
        db.flush()
        tenant = TenantClient(
            client_id="tenant-b",
            jurisdiction_id=jurisdiction.id,
            city_name="Tenant B",
            department_name="Planning & Zoning Department",
            standard_letter_fee_cents=7500,
            comprehensive_letter_fee_cents=15000,
            expedited_fee_cents=5000,
        )
        db.add(tenant)
        db.commit()

        ensure_default_email_templates(db)
        default_template = db.query(EmailTemplate).filter_by(code="approved", is_system_default=True).one()
        db.add(
            EmailTemplate(
                jurisdiction_id=jurisdiction.id,
                tenant_client_id=tenant.id,
                owner_organization_id=tenant.client_id,
                base_template_id=default_template.id,
                code="approved",
                trigger_state="approved",
                name="Approved Override",
                description="Customer-specific approval notice.",
                category="request_updates",
                subject_template="Tenant B approved {{request_id}}",
                body_template="<p>Tenant B custom approval email.</p>",
                status="active",
                version=1,
                created_by_user_id=None,
                is_system_default=False,
            )
        )
        db.commit()

        effective = get_effective_email_templates(db, tenant)
        approved = next(item for item in effective if item.template.code == "approved")
        active_template = get_active_email_template_for_client(
            db,
            tenant_client=tenant,
            template_code="approved",
        )

        assert approved.override_template is not None
        assert approved.template.name == "Approved Override"
        assert active_template is not None
        assert active_template.subject_template == "Tenant B approved {{request_id}}"
    finally:
        db.close()
