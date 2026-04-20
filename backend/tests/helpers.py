"""Shared test helpers for backend route coverage."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Jurisdiction, Property, PropertySnapshot, Request, TenantClient, User


def make_db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_local()


def add_jurisdiction(
    db: Session,
    *,
    id: str = "jur-1",
    code: str = "dream-town",
    name: str = "Dream Town",
    department_name: str = "Planning",
    timezone: str = "UTC",
    public_site_title: str | None = None,
    public_contact_email: str | None = None,
) -> Jurisdiction:
    jurisdiction = Jurisdiction(
        id=id,
        code=code,
        name=name,
        department_name=department_name,
        timezone=timezone,
        public_site_title=public_site_title,
        public_contact_email=public_contact_email,
    )
    db.add(jurisdiction)
    db.commit()
    return jurisdiction


def add_user(
    db: Session,
    *,
    id: str = "user-1",
    email: str = "user@example.com",
    first_name: str = "User",
    last_name: str = "One",
    clerk_user_id: str | None = None,
    is_active: bool = True,
) -> User:
    user = User(
        id=id,
        email=email,
        clerk_user_id=clerk_user_id,
        password_hash="hash",
        first_name=first_name,
        last_name=last_name,
        is_active=is_active,
        email_verified_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(user)
    db.commit()
    return user


def add_tenant_client(
    db: Session,
    *,
    id: str = "tenant-1",
    client_id: str = "dream-town",
    clerk_organization_id: str | None = "org_dream_town",
    jurisdiction_id: str | None = "jur-1",
    city_name: str = "Dream Town",
    department_name: str = "Planning",
    is_active: bool = True,
    settings_json: dict | None = None,
) -> TenantClient:
    tenant = TenantClient(
        id=id,
        client_id=client_id,
        clerk_organization_id=clerk_organization_id,
        jurisdiction_id=jurisdiction_id,
        city_name=city_name,
        department_name=department_name,
        standard_letter_fee_cents=7500,
        comprehensive_letter_fee_cents=15000,
        expedited_fee_cents=5000,
        is_active=is_active,
        settings_json=settings_json,
    )
    db.add(tenant)
    db.commit()
    return tenant


def add_property(
    db: Session,
    *,
    id: str = "prop-1",
    jurisdiction_id: str = "jur-1",
    source_system: str = "gridics",
    address_line1: str = "100 Main Street",
    city: str = "Dream Town",
    state: str = "IL",
    apn: str | None = "APN-1",
    group_id: str | None = "group-1",
) -> Property:
    property_record = Property(
        id=id,
        jurisdiction_id=jurisdiction_id,
        source_system=source_system,
        source_property_id="source-1",
        group_id=group_id,
        apn=apn,
        address_line1=address_line1,
        city=city,
        state=state,
        postal_code="12345",
        latitude=39.78,
        longitude=-89.64,
    )
    db.add(property_record)
    db.commit()
    return property_record


def add_property_snapshot(
    db: Session,
    *,
    id: str = "snap-1",
    property_id: str = "prop-1",
    captured_by_user_id: str | None = "user-1",
    capture_reason: str = "manual",
    address: str = "100 Main Street",
) -> PropertySnapshot:
    snapshot = PropertySnapshot(
        id=id,
        property_id=property_id,
        captured_by_user_id=captured_by_user_id,
        capture_reason=capture_reason,
        address=address,
        apn="APN-1",
        group_id="group-1",
        zoning_code="R-1",
        zoning_name="Residential",
        lot_size_sf=10000,
        permitted_uses_json={"uses": ["residential"]},
        restrictions_json={"setbacks": "10"},
        overlays_json={"overlay": "none"},
        raw_source_payload_json={"source": "gridics"},
        source_payload_hash="hash-1",
    )
    db.add(snapshot)
    db.commit()
    return snapshot


def add_request(
    db: Session,
    *,
    id: str = "req-1",
    public_id: str = "ZVL-2026-000001",
    jurisdiction_id: str = "jur-1",
    requester_user_id: str = "user-1",
    property_id: str = "prop-1",
    property_snapshot_id: str = "snap-1",
    status: str = "draft",
    payment_status: str = "unpaid",
    assigned_to_user_id: str | None = None,
    current_quote_id: str | None = None,
    current_draft_id: str | None = None,
    final_letter_version_id: str | None = None,
) -> Request:
    request = Request(
        id=id,
        public_id=public_id,
        jurisdiction_id=jurisdiction_id,
        requester_user_id=requester_user_id,
        property_id=property_id,
        property_snapshot_id=property_snapshot_id,
        letter_type="standard",
        processing_type="standard",
        delivery_method="email",
        status=status,
        payment_status=payment_status,
        assigned_to_user_id=assigned_to_user_id,
        requester_first_name="Ada",
        requester_last_name="Lovelace",
        requester_email="ada@example.com",
        requester_phone="555-0100",
        requester_organization="Dream Town LLC",
        mailing_address_json={"line1": "100 Main Street"},
        special_instructions=None,
        total_amount_cents=0,
        currency="USD",
        current_quote_id=current_quote_id,
        current_draft_id=current_draft_id,
        final_letter_version_id=final_letter_version_id,
    )
    db.add(request)
    db.commit()
    return request


def make_temp_pdf(path: Path, content: bytes = b"%PDF-1.4 test pdf") -> Path:
    path.write_bytes(content)
    return path
