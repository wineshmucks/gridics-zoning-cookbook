"""Initial SQLAlchemy models for UZone."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def uuid_pk() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class User(Base, TimestampMixin):
    __tablename__ = "shared_users"

    id: Mapped[str] = uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    clerk_user_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    organization: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class Role(Base, TimestampMixin):
    __tablename__ = "shared_roles"

    id: Mapped[str] = uuid_pk()
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class UserRole(Base):
    __tablename__ = "shared_user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),)

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("shared_users.id"), nullable=False)
    role_id: Mapped[str] = mapped_column(ForeignKey("shared_roles.id"), nullable=False)
    granted_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("shared_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Session(Base):
    __tablename__ = "shared_sessions"

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("shared_users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Jurisdiction(Base, TimestampMixin):
    __tablename__ = "shared_jurisdictions"

    id: Mapped[str] = uuid_pk()
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    department_name: Mapped[str] = mapped_column(String(255), nullable=False)
    public_site_title: Mapped[str | None] = mapped_column(String(255))
    public_contact_email: Mapped[str | None] = mapped_column(String(255))
    public_contact_phone: Mapped[str | None] = mapped_column(String(50))
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    settings_json: Mapped[dict | None] = mapped_column(JSON)


class TenantClient(Base, TimestampMixin):
    __tablename__ = "shared_tenant_clients"

    id: Mapped[str] = uuid_pk()
    client_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    clerk_organization_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    jurisdiction_id: Mapped[str | None] = mapped_column(ForeignKey("shared_jurisdictions.id"))
    city_name: Mapped[str] = mapped_column(String(255), nullable=False)
    department_name: Mapped[str] = mapped_column(String(255), nullable=False)
    standard_letter_fee_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comprehensive_letter_fee_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expedited_fee_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    support_phone: Mapped[str | None] = mapped_column(String(50))
    support_email: Mapped[str | None] = mapped_column(String(255))
    contact_address: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    settings_json: Mapped[dict | None] = mapped_column(JSON)


class TenantDomain(Base, TimestampMixin):
    __tablename__ = "shared_tenant_domains"
    __table_args__ = (UniqueConstraint("hostname", name="uq_tenant_domains_hostname"),)

    id: Mapped[str] = uuid_pk()
    tenant_client_id: Mapped[str] = mapped_column(ForeignKey("shared_tenant_clients.id"), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class PlatformSetting(Base, TimestampMixin):
    __tablename__ = "shared_platform_settings"

    id: Mapped[str] = uuid_pk()
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    json_value: Mapped[dict | None] = mapped_column(JSON)


class AssistantMessageFeedback(Base, TimestampMixin):
    __tablename__ = "agentic_assistant_message_feedback"
    __table_args__ = (
        UniqueConstraint(
            "tenant_client_id",
            "conversation_id",
            "message_id",
            name="uq_assistant_message_feedback_conversation_message",
        ),
    )

    id: Mapped[str] = uuid_pk()
    tenant_client_id: Mapped[str] = mapped_column(ForeignKey("shared_tenant_clients.id"), nullable=False)
    clerk_user_id: Mapped[str | None] = mapped_column(String(255))
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)
    surface: Mapped[str] = mapped_column(String(100), nullable=False, default="public-assistant")
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(255))
    feedback_value: Mapped[str] = mapped_column(String(10), nullable=False)
    message_excerpt: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class ZoningCodeIngestionRun(Base, TimestampMixin):
    __tablename__ = "agentic_zoning_code_ingestion_runs"

    id: Mapped[str] = uuid_pk()
    tenant_client_id: Mapped[str] = mapped_column(ForeignKey("shared_tenant_clients.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    pages_crawled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    documents_extracted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sections_extracted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunks_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class ZoningCodeDocument(Base, TimestampMixin):
    __tablename__ = "agentic_zoning_code_documents"
    __table_args__ = (
        UniqueConstraint("tenant_client_id", "source_url", name="uq_zoning_code_documents_source"),
    )

    id: Mapped[str] = uuid_pk()
    tenant_client_id: Mapped[str] = mapped_column(ForeignKey("shared_tenant_clients.id"), nullable=False)
    ingestion_run_id: Mapped[str | None] = mapped_column(ForeignKey("agentic_zoning_code_ingestion_runs.id"))
    source_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_path: Mapped[str | None] = mapped_column(String(1000))
    source_title: Mapped[str | None] = mapped_column(String(500))
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fetch_status_code: Mapped[int | None] = mapped_column(Integer)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ZoningCodeSection(Base, TimestampMixin):
    __tablename__ = "agentic_zoning_code_sections"
    __table_args__ = (
        UniqueConstraint("tenant_client_id", "section_key", name="uq_zoning_code_sections_key"),
    )

    id: Mapped[str] = uuid_pk()
    tenant_client_id: Mapped[str] = mapped_column(ForeignKey("shared_tenant_clients.id"), nullable=False)
    ingestion_run_id: Mapped[str | None] = mapped_column(ForeignKey("agentic_zoning_code_ingestion_runs.id"))
    document_id: Mapped[str] = mapped_column(ForeignKey("agentic_zoning_code_documents.id"), nullable=False)
    section_key: Mapped[str] = mapped_column(String(500), nullable=False)
    section_title: Mapped[str] = mapped_column(String(500), nullable=False)
    section_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    section_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    section_path: Mapped[str | None] = mapped_column(String(1000))
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_anchor: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class Property(Base, TimestampMixin):
    __tablename__ = "shared_properties"

    id: Mapped[str] = uuid_pk()
    jurisdiction_id: Mapped[str] = mapped_column(ForeignKey("shared_jurisdictions.id"), nullable=False)
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    source_property_id: Mapped[str | None] = mapped_column(String(255))
    group_id: Mapped[str | None] = mapped_column(String(255))
    apn: Mapped[str | None] = mapped_column(String(255))
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(20))
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7))


class PropertySnapshot(Base):
    __tablename__ = "shared_property_snapshots"

    id: Mapped[str] = uuid_pk()
    property_id: Mapped[str] = mapped_column(ForeignKey("shared_properties.id"), nullable=False)
    captured_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("shared_users.id"))
    capture_reason: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    apn: Mapped[str | None] = mapped_column(String(255))
    group_id: Mapped[str | None] = mapped_column(String(255))
    zoning_code: Mapped[str | None] = mapped_column(String(100))
    zoning_name: Mapped[str | None] = mapped_column(String(255))
    lot_size_sf: Mapped[int | None] = mapped_column(Integer)
    permitted_uses_json: Mapped[dict | list | None] = mapped_column(JSON)
    restrictions_json: Mapped[dict | list | None] = mapped_column(JSON)
    overlays_json: Mapped[dict | list | None] = mapped_column(JSON)
    raw_source_payload_json: Mapped[dict | list | None] = mapped_column(JSON)
    source_payload_hash: Mapped[str | None] = mapped_column(String(64))
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Request(Base, TimestampMixin):
    __tablename__ = "letters_requests"

    id: Mapped[str] = uuid_pk()
    public_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    jurisdiction_id: Mapped[str] = mapped_column(ForeignKey("shared_jurisdictions.id"), nullable=False)
    requester_user_id: Mapped[str] = mapped_column(ForeignKey("shared_users.id"), nullable=False)
    property_id: Mapped[str] = mapped_column(ForeignKey("shared_properties.id"), nullable=False)
    property_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("shared_property_snapshots.id"), nullable=False
    )
    letter_type: Mapped[str] = mapped_column(String(50), nullable=False)
    processing_type: Mapped[str] = mapped_column(String(50), nullable=False)
    delivery_method: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(50), nullable=False)
    assigned_to_user_id: Mapped[str | None] = mapped_column(ForeignKey("shared_users.id"))
    requester_first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    requester_last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    requester_email: Mapped[str] = mapped_column(String(255), nullable=False)
    requester_phone: Mapped[str | None] = mapped_column(String(50))
    requester_organization: Mapped[str | None] = mapped_column(String(255))
    mailing_address_json: Mapped[dict | None] = mapped_column(JSON)
    special_instructions: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime)
    total_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    current_quote_id: Mapped[str | None] = mapped_column(ForeignKey("letters_quotes.id"))
    current_draft_id: Mapped[str | None] = mapped_column(ForeignKey("letters_letter_drafts.id"))
    final_letter_version_id: Mapped[str | None] = mapped_column(ForeignKey("letters_letter_versions.id"))


class RequestStatusEvent(Base):
    __tablename__ = "letters_request_status_events"

    id: Mapped[str] = uuid_pk()
    request_id: Mapped[str] = mapped_column(ForeignKey("letters_requests.id"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(50))
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(100))
    reason_text: Mapped[str | None] = mapped_column(Text)
    acted_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("shared_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class RequestAssignment(Base):
    __tablename__ = "letters_request_assignments"

    id: Mapped[str] = uuid_pk()
    request_id: Mapped[str] = mapped_column(ForeignKey("letters_requests.id"), nullable=False)
    assigned_to_user_id: Mapped[str] = mapped_column(ForeignKey("shared_users.id"), nullable=False)
    assigned_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("shared_users.id"))
    assignment_reason: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class RequestNote(Base, TimestampMixin):
    __tablename__ = "letters_request_notes"

    id: Mapped[str] = uuid_pk()
    request_id: Mapped[str] = mapped_column(ForeignKey("letters_requests.id"), nullable=False)
    author_user_id: Mapped[str] = mapped_column(ForeignKey("shared_users.id"), nullable=False)
    note_type: Mapped[str] = mapped_column(String(50), nullable=False)
    visibility: Mapped[str] = mapped_column(String(50), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)


class FeeSchedule(Base, TimestampMixin):
    __tablename__ = "letters_fee_schedules"

    id: Mapped[str] = uuid_pk()
    jurisdiction_id: Mapped[str] = mapped_column(ForeignKey("shared_jurisdictions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    effective_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    effective_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("shared_users.id"))


class FeeScheduleItem(Base, TimestampMixin):
    __tablename__ = "letters_fee_schedule_items"

    id: Mapped[str] = uuid_pk()
    fee_schedule_id: Mapped[str] = mapped_column(ForeignKey("letters_fee_schedules.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    fee_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    applies_to_letter_type: Mapped[str | None] = mapped_column(String(50))
    applies_to_processing_type: Mapped[str | None] = mapped_column(String(50))
    applies_to_delivery_method: Mapped[str | None] = mapped_column(String(50))
    tax_mode: Mapped[str | None] = mapped_column(String(50))
    charge_unit: Mapped[str | None] = mapped_column(String(50))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class Quote(Base):
    __tablename__ = "letters_quotes"

    id: Mapped[str] = uuid_pk()
    request_id: Mapped[str] = mapped_column(ForeignKey("letters_requests.id"), nullable=False)
    fee_schedule_id: Mapped[str] = mapped_column(ForeignKey("letters_fee_schedules.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    line_items_json: Mapped[list | dict] = mapped_column(JSON, nullable=False)
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Payment(Base, TimestampMixin):
    __tablename__ = "letters_payments"

    id: Mapped[str] = uuid_pk()
    request_id: Mapped[str] = mapped_column(ForeignKey("letters_requests.id"), nullable=False)
    quote_id: Mapped[str] = mapped_column(ForeignKey("letters_quotes.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_payment_id: Mapped[str | None] = mapped_column(String(255))
    provider_checkout_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_message: Mapped[str | None] = mapped_column(Text)
    receipt_url: Mapped[str | None] = mapped_column(String(1000))


class PaymentEvent(Base):
    __tablename__ = "letters_payment_events"
    __table_args__ = (UniqueConstraint("provider_event_id", name="uq_payment_events_provider_event_id"),)

    id: Mapped[str] = uuid_pk()
    payment_id: Mapped[str] = mapped_column(ForeignKey("letters_payments.id"), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class LetterTemplate(Base, TimestampMixin):
    __tablename__ = "letters_letter_templates"

    id: Mapped[str] = uuid_pk()
    jurisdiction_id: Mapped[str] = mapped_column(ForeignKey("shared_jurisdictions.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    letter_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    template_body: Mapped[str] = mapped_column(Text, nullable=False)
    merge_variables_json: Mapped[list | dict | None] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("shared_users.id"))


class LetterDraft(Base, TimestampMixin):
    __tablename__ = "letters_letter_drafts"

    id: Mapped[str] = uuid_pk()
    request_id: Mapped[str] = mapped_column(ForeignKey("letters_requests.id"), nullable=False)
    template_id: Mapped[str] = mapped_column(ForeignKey("letters_letter_templates.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    generated_body: Mapped[str] = mapped_column(Text, nullable=False)
    editable_sections_json: Mapped[list | dict | None] = mapped_column(JSON)
    generated_from_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("shared_property_snapshots.id")
    )
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("shared_users.id"))
    updated_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("shared_users.id"))


class LetterVersion(Base):
    __tablename__ = "letters_letter_versions"

    id: Mapped[str] = uuid_pk()
    request_id: Mapped[str] = mapped_column(ForeignKey("letters_requests.id"), nullable=False)
    draft_id: Mapped[str | None] = mapped_column(ForeignKey("letters_letter_drafts.id"))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_type: Mapped[str] = mapped_column(String(50), nullable=False)
    html_body: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_storage_key: Mapped[str | None] = mapped_column(String(1000))
    pdf_sha256: Mapped[str | None] = mapped_column(String(64))
    signed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("shared_users.id"))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Delivery(Base, TimestampMixin):
    __tablename__ = "letters_deliveries"

    id: Mapped[str] = uuid_pk()
    request_id: Mapped[str] = mapped_column(ForeignKey("letters_requests.id"), nullable=False)
    letter_version_id: Mapped[str] = mapped_column(ForeignKey("letters_letter_versions.id"), nullable=False)
    delivery_method: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    destination: Mapped[str] = mapped_column(String(1000), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(255))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
    failure_reason: Mapped[str | None] = mapped_column(Text)


class EmailTemplate(Base, TimestampMixin):
    __tablename__ = "letters_email_templates"

    id: Mapped[str] = uuid_pk()
    jurisdiction_id: Mapped[str | None] = mapped_column(ForeignKey("shared_jurisdictions.id"))
    tenant_client_id: Mapped[str | None] = mapped_column(ForeignKey("shared_tenant_clients.id"))
    owner_organization_id: Mapped[str | None] = mapped_column(String(255))
    base_template_id: Mapped[str | None] = mapped_column(ForeignKey("letters_email_templates.id"))
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_state: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="request_updates")
    subject_template: Mapped[str] = mapped_column(Text, nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("shared_users.id"))
    is_system_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class JurisdictionHomePageContent(Base, TimestampMixin):
    __tablename__ = "letters_jurisdiction_home_page_content"

    id: Mapped[str] = uuid_pk()
    jurisdiction_id: Mapped[str] = mapped_column(ForeignKey("shared_jurisdictions.id"), nullable=False, unique=True)
    hero_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    services_json: Mapped[list] = mapped_column(JSON, nullable=False)
    about_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    faq_json: Mapped[list] = mapped_column(JSON, nullable=False)
    contact_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class EmailEvent(Base):
    __tablename__ = "letters_email_events"

    id: Mapped[str] = uuid_pk()
    request_id: Mapped[str | None] = mapped_column(ForeignKey("letters_requests.id"))
    template_id: Mapped[str | None] = mapped_column(ForeignKey("letters_email_templates.id"))
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject_rendered: Mapped[str] = mapped_column(Text, nullable=False)
    body_rendered: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(100))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "letters_audit_log"

    id: Mapped[str] = uuid_pk()
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("shared_users.id"))
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    before_json: Mapped[dict | list | None] = mapped_column(JSON)
    after_json: Mapped[dict | list | None] = mapped_column(JSON)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
