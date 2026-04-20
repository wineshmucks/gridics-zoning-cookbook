"""Coverage for database size and dangling-record maintenance helpers."""

from __future__ import annotations

from sqlalchemy import select

from app.api.v1 import admin
import app.services.database_maintenance_service as database_maintenance_service
from app.db.models import (
    AssistantMessageFeedback,
    Delivery,
    EmailEvent,
    EmailTemplate,
    FeeSchedule,
    FeeScheduleItem,
    JurisdictionHomePageContent,
    LetterDraft,
    LetterTemplate,
    LetterVersion,
    Payment,
    PaymentEvent,
    Property,
    PropertySnapshot,
    Quote,
    Request,
    RequestAssignment,
    RequestNote,
    RequestStatusEvent,
    TenantClient,
    TenantDomain,
    ZoningCodeDocument,
    ZoningCodeIngestionRun,
    ZoningCodeSection,
)
from app.services.database_maintenance_service import cleanup_dangling_records, get_database_info

from .helpers import add_jurisdiction, add_tenant_client, add_user, make_db


def test_database_info_reports_table_sizes_and_dangling_rows(monkeypatch) -> None:
    db = make_db()
    try:
        add_jurisdiction(db, id="jur-valid", code="valid-town", name="Valid Town")
        add_tenant_client(
            db,
            id="tenant-valid",
            client_id="valid-town",
            clerk_organization_id="org_valid",
            jurisdiction_id="jur-valid",
        )
        add_tenant_client(
            db,
            id="tenant-dangling",
            client_id="dangling-town",
            clerk_organization_id="org_dangling",
            jurisdiction_id="missing-jur",
        )
        db.add(
            Property(
                id="prop-dangling",
                jurisdiction_id="missing-jur",
                source_system="gridics",
                source_property_id="source-1",
                group_id=None,
                apn="APN-1",
                address_line1="100 Main Street",
                address_line2=None,
                city="Dangling Town",
                state="IL",
                postal_code="12345",
                latitude=39.78,
                longitude=-89.64,
            )
        )
        db.commit()

        monkeypatch.setattr(
            database_maintenance_service,
            "_schema_table_summaries",
            lambda db_session, schema: [
                database_maintenance_service.DatabaseTableSummary(
                    table_name="aos_sessions",
                    row_count=3,
                    size_bytes=2048,
                    size_label="2.0 KB",
                )
            ] if schema == "agent_os" else [],
        )

        info = get_database_info(db)

        table_names = {item.table_name for item in info.tables}
        agno_table_names = {item.table_name for item in info.agno_tables}
        dangling_tables = {item.table_name: item for item in info.dangling_tables}

        assert "shared_tenant_clients" in table_names
        assert "shared_properties" in table_names
        assert "aos_sessions" in agno_table_names
        assert "shared_tenant_clients" in dangling_tables
        assert "shared_properties" in dangling_tables
        assert dangling_tables["shared_tenant_clients"].dangling_rows == 1
        assert dangling_tables["shared_properties"].dangling_rows == 1
        assert info.total_size_bytes is None or info.total_size_bytes >= 0
    finally:
        db.close()


def test_cleanup_dangling_records_deletes_dangling_graphs_and_keeps_valid_rows() -> None:
    db = make_db()
    try:
        add_jurisdiction(db, id="jur-valid", code="valid-town", name="Valid Town")
        add_user(db, id="user-valid", email="user@example.com")

        valid_tenant = add_tenant_client(
            db,
            id="tenant-valid",
            client_id="valid-town",
            clerk_organization_id="org_valid",
            jurisdiction_id="jur-valid",
        )
        db.add(TenantDomain(id="tenant-domain-valid", tenant_client_id=valid_tenant.id, hostname="valid.example.com"))
        db.add(AssistantMessageFeedback(id="feedback-valid", tenant_client_id=valid_tenant.id, agent_id="assistant", surface="public-assistant", conversation_id="c-valid", message_id="m-valid", feedback_value="positive"))
        db.add(
            ZoningCodeIngestionRun(
                id="run-valid",
                tenant_client_id=valid_tenant.id,
                mode="ingest",
                status="completed",
                source_url="https://example.com/valid",
                pages_crawled=1,
                documents_extracted=1,
                sections_extracted=1,
                chunks_upserted=1,
            )
        )
        db.add(
            ZoningCodeDocument(
                id="doc-valid",
                tenant_client_id=valid_tenant.id,
                ingestion_run_id="run-valid",
                source_url="https://example.com/doc",
                source_hash="hash-valid",
                raw_text="valid",
            )
        )
        db.add(
            ZoningCodeSection(
                id="section-valid",
                tenant_client_id=valid_tenant.id,
                ingestion_run_id="run-valid",
                document_id="doc-valid",
                section_key="section-valid",
                section_title="Section",
                section_level=1,
                section_order=0,
                normalized_text="text",
                content_hash="content-hash",
            )
        )
        db.add(
            JurisdictionHomePageContent(
                id="homepage-valid",
                jurisdiction_id="jur-valid",
                hero_json={"title": "Valid"},
                services_json=[],
                about_json={},
                faq_json=[],
                contact_json={},
            )
        )

        dangling_tenant = add_tenant_client(
            db,
            id="tenant-dangling",
            client_id="dangling-town",
            clerk_organization_id="org_dangling",
            jurisdiction_id="missing-jur",
        )
        dangling_tenant_id = dangling_tenant.id
        db.add(TenantDomain(id="tenant-domain-dangling", tenant_client_id=dangling_tenant.id, hostname="dangling.example.com"))
        db.add(
            AssistantMessageFeedback(
                id="feedback-dangling",
                tenant_client_id=dangling_tenant.id,
                agent_id="assistant",
                surface="public-assistant",
                conversation_id="c-dangling",
                message_id="m-dangling",
                feedback_value="negative",
            )
        )
        db.add(
            ZoningCodeIngestionRun(
                id="run-dangling",
                tenant_client_id=dangling_tenant.id,
                mode="ingest",
                status="failed",
                source_url="https://example.com/dangling",
                pages_crawled=2,
                documents_extracted=1,
                sections_extracted=1,
                chunks_upserted=0,
            )
        )
        db.add(
            ZoningCodeDocument(
                id="doc-dangling",
                tenant_client_id=dangling_tenant.id,
                ingestion_run_id="run-dangling",
                source_url="https://example.com/dangling/doc",
                source_hash="hash-dangling",
                raw_text="dangling",
            )
        )
        db.add(
            ZoningCodeSection(
                id="section-dangling",
                tenant_client_id=dangling_tenant.id,
                ingestion_run_id="run-dangling",
                document_id="doc-dangling",
                section_key="section-dangling",
                section_title="Section",
                section_level=1,
                section_order=0,
                normalized_text="text",
                content_hash="content-hash-dangling",
            )
        )
        db.add(
            EmailTemplate(
                id="email-template-dangling",
                jurisdiction_id="missing-jur",
                tenant_client_id=dangling_tenant.id,
                owner_organization_id=dangling_tenant.clerk_organization_id,
                code="request-submitted",
                trigger_state="submitted",
                name="Submitted",
                category="request_updates",
                subject_template="Subject",
                body_template="Body",
                status="active",
                version=1,
            )
        )

        add_user(db, id="requester", email="requester@example.com")
        db.add(
            Property(
                id="prop-dangling",
                jurisdiction_id="missing-jur",
                source_system="gridics",
                source_property_id="source-1",
                group_id=None,
                apn="APN-1",
                address_line1="100 Main Street",
                address_line2=None,
                city="Dangling Town",
                state="IL",
                postal_code="12345",
                latitude=39.78,
                longitude=-89.64,
            )
        )
        db.add(
            PropertySnapshot(
                id="snapshot-dangling",
                property_id="prop-dangling",
                captured_by_user_id="user-valid",
                capture_reason="manual",
                address="100 Main Street",
                apn="APN-1",
                group_id=None,
                zoning_code="R-1",
                zoning_name="Residential",
                lot_size_sf=10000,
                permitted_uses_json={"uses": ["residential"]},
                restrictions_json={},
                overlays_json={},
                raw_source_payload_json={},
                source_payload_hash="hash",
            )
        )
        db.add(
            FeeSchedule(
                id="fee-schedule-dangling",
                jurisdiction_id="missing-jur",
                name="Dangling Schedule",
                status="active",
            )
        )
        db.add(
            LetterTemplate(
                id="letter-template-dangling",
                jurisdiction_id="missing-jur",
                code="standard",
                name="Standard",
                letter_type="standard",
                status="active",
                template_body="Body",
                version=1,
            )
        )
        db.add(
            Request(
                id="request-dangling",
                public_id="REQ-DANGLING",
                jurisdiction_id="missing-jur",
                requester_user_id="requester",
                property_id="prop-dangling",
                property_snapshot_id="snapshot-dangling",
                letter_type="standard",
                processing_type="standard",
                delivery_method="email",
                status="draft",
                payment_status="unpaid",
                requester_first_name="Ada",
                requester_last_name="Lovelace",
                requester_email="ada@example.com",
                requester_phone="555-0100",
                requester_organization=None,
                mailing_address_json={"line1": "100 Main Street"},
                special_instructions=None,
                total_amount_cents=0,
                currency="USD",
            )
        )
        db.add(RequestNote(id="request-note-dangling", request_id="request-dangling", author_user_id="requester", note_type="internal", visibility="internal", body="note"))
        db.add(RequestAssignment(id="request-assignment-dangling", request_id="request-dangling", assigned_to_user_id="requester"))
        db.add(RequestStatusEvent(id="request-status-event-dangling", request_id="request-dangling", to_status="submitted"))
        db.add(
            Quote(
                id="quote-dangling",
                request_id="request-dangling",
                fee_schedule_id="fee-schedule-dangling",
                status="generated",
                line_items_json=[],
                subtotal_cents=0,
                tax_cents=0,
                total_cents=0,
                currency="USD",
            )
        )
        db.add(
            Payment(
                id="payment-dangling",
                request_id="request-dangling",
                quote_id="quote-dangling",
                provider="stripe",
                status="pending",
                amount_cents=0,
                currency="USD",
            )
        )
        db.add(
            PaymentEvent(
                id="payment-event-dangling",
                payment_id="payment-dangling",
                provider_event_id="evt-dangling",
                event_type="payment_intent.succeeded",
                payload_json={"id": "evt-dangling"},
            )
        )
        db.add(
            LetterDraft(
                id="letter-draft-dangling",
                request_id="request-dangling",
                template_id="letter-template-dangling",
                status="draft",
                generated_body="draft",
            )
        )
        db.add(
            LetterVersion(
                id="letter-version-dangling",
                request_id="request-dangling",
                draft_id="letter-draft-dangling",
                version_number=1,
                version_type="final",
                html_body="<p>draft</p>",
            )
        )
        db.add(
            Delivery(
                id="delivery-dangling",
                request_id="request-dangling",
                letter_version_id="letter-version-dangling",
                delivery_method="email",
                status="queued",
                destination="ada@example.com",
            )
        )
        db.add(
            EmailEvent(
                id="email-event-dangling",
                request_id="request-dangling",
                template_id="email-template-dangling",
                recipient_email="ada@example.com",
                subject_rendered="Subject",
                body_rendered="Body",
                status="queued",
            )
        )
        db.commit()

        result = cleanup_dangling_records(db)

        deleted_tables = {item.table_name for item in result.deleted_by_table}
        assert result.deleted_rows_total > 0
        assert "shared_tenant_clients" in deleted_tables
        assert "letters_requests" in deleted_tables
        assert "shared_property_snapshots" in deleted_tables
        assert "letters_quotes" in deleted_tables
        assert "letters_payments" in deleted_tables
        assert "letters_email_templates" in deleted_tables

        assert db.get(TenantClient, dangling_tenant_id) is None
        assert db.get(TenantDomain, "tenant-domain-dangling") is None
        assert db.get(AssistantMessageFeedback, "feedback-dangling") is None
        assert db.get(ZoningCodeIngestionRun, "run-dangling") is None
        assert db.get(ZoningCodeDocument, "doc-dangling") is None
        assert db.get(ZoningCodeSection, "section-dangling") is None
        assert db.get(Property, "prop-dangling") is None
        assert db.get(PropertySnapshot, "snapshot-dangling") is None
        assert db.get(Request, "request-dangling") is None
        assert db.get(RequestNote, "request-note-dangling") is None
        assert db.get(RequestAssignment, "request-assignment-dangling") is None
        assert db.get(RequestStatusEvent, "request-status-event-dangling") is None
        assert db.get(Quote, "quote-dangling") is None
        assert db.get(Payment, "payment-dangling") is None
        assert db.get(PaymentEvent, "payment-event-dangling") is None
        assert db.get(LetterDraft, "letter-draft-dangling") is None
        assert db.get(LetterVersion, "letter-version-dangling") is None
        assert db.get(Delivery, "delivery-dangling") is None
        assert db.get(EmailEvent, "email-event-dangling") is None
        assert db.get(FeeSchedule, "fee-schedule-dangling") is None
        assert db.get(FeeScheduleItem, "fee-schedule-item-dangling") is None
        assert db.get(LetterTemplate, "letter-template-dangling") is None
        assert db.get(EmailTemplate, "email-template-dangling") is None
        assert db.get(JurisdictionHomePageContent, "homepage-valid") is not None
        assert db.get(TenantClient, valid_tenant.id) is not None
    finally:
        db.close()
