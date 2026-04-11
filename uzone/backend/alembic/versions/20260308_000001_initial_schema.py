"""Initial UZone schema."""

from alembic import op
import sqlalchemy as sa


revision = "20260308_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("clerk_user_id", sa.String(length=255), unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=50)),
        sa.Column("organization", sa.String(length=255)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email_verified_at", sa.DateTime()),
        sa.Column("last_login_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "jurisdictions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("department_name", sa.String(length=255), nullable=False),
        sa.Column("public_site_title", sa.String(length=255)),
        sa.Column("public_contact_email", sa.String(length=255)),
        sa.Column("public_contact_phone", sa.String(length=50)),
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("settings_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "user_roles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role_id", sa.String(length=36), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("granted_by_user_id", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime()),
        sa.Column("ip_address", sa.String(length=64)),
        sa.Column("user_agent", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "properties",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("jurisdiction_id", sa.String(length=36), sa.ForeignKey("jurisdictions.id"), nullable=False),
        sa.Column("source_system", sa.String(length=100), nullable=False),
        sa.Column("source_property_id", sa.String(length=255)),
        sa.Column("group_id", sa.String(length=255)),
        sa.Column("apn", sa.String(length=255)),
        sa.Column("address_line1", sa.String(length=255), nullable=False),
        sa.Column("address_line2", sa.String(length=255)),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=50), nullable=False),
        sa.Column("postal_code", sa.String(length=20)),
        sa.Column("latitude", sa.Numeric(10, 7)),
        sa.Column("longitude", sa.Numeric(10, 7)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_properties_jurisdiction_apn", "properties", ["jurisdiction_id", "apn"])
    op.create_index("ix_properties_jurisdiction_group_id", "properties", ["jurisdiction_id", "group_id"])
    op.create_table(
        "property_snapshots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("property_id", sa.String(length=36), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("captured_by_user_id", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("capture_reason", sa.String(length=100), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("apn", sa.String(length=255)),
        sa.Column("group_id", sa.String(length=255)),
        sa.Column("zoning_code", sa.String(length=100)),
        sa.Column("zoning_name", sa.String(length=255)),
        sa.Column("lot_size_sf", sa.Integer()),
        sa.Column("permitted_uses_json", sa.JSON()),
        sa.Column("restrictions_json", sa.JSON()),
        sa.Column("overlays_json", sa.JSON()),
        sa.Column("raw_source_payload_json", sa.JSON()),
        sa.Column("source_payload_hash", sa.String(length=64)),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "fee_schedules",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("jurisdiction_id", sa.String(length=36), sa.ForeignKey("jurisdictions.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("effective_start_at", sa.DateTime()),
        sa.Column("effective_end_at", sa.DateTime()),
        sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "letter_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("jurisdiction_id", sa.String(length=36), sa.ForeignKey("jurisdictions.id"), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("letter_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("template_body", sa.Text(), nullable=False),
        sa.Column("merge_variables_json", sa.JSON()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "email_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("jurisdiction_id", sa.String(length=36), sa.ForeignKey("jurisdictions.id"), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("subject_template", sa.Text(), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "quotes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("fee_schedule_id", sa.String(length=36), sa.ForeignKey("fee_schedules.id"), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("line_items_json", sa.JSON(), nullable=False),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False),
        sa.Column("tax_cents", sa.Integer(), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "letter_drafts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), sa.ForeignKey("letter_templates.id"), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("generated_body", sa.Text(), nullable=False),
        sa.Column("editable_sections_json", sa.JSON()),
        sa.Column("generated_from_snapshot_id", sa.String(length=36), sa.ForeignKey("property_snapshots.id")),
        sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("updated_by_user_id", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "letter_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("draft_id", sa.String(length=36), sa.ForeignKey("letter_drafts.id")),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("version_type", sa.String(length=50), nullable=False),
        sa.Column("html_body", sa.Text(), nullable=False),
        sa.Column("pdf_storage_key", sa.String(length=1000)),
        sa.Column("pdf_sha256", sa.String(length=64)),
        sa.Column("signed_by_user_id", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("signed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("public_id", sa.String(length=50), nullable=False, unique=True),
        sa.Column("jurisdiction_id", sa.String(length=36), sa.ForeignKey("jurisdictions.id"), nullable=False),
        sa.Column("requester_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("property_id", sa.String(length=36), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("property_snapshot_id", sa.String(length=36), sa.ForeignKey("property_snapshots.id"), nullable=False),
        sa.Column("letter_type", sa.String(length=50), nullable=False),
        sa.Column("processing_type", sa.String(length=50), nullable=False),
        sa.Column("delivery_method", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("payment_status", sa.String(length=50), nullable=False),
        sa.Column("assigned_to_user_id", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("requester_first_name", sa.String(length=100), nullable=False),
        sa.Column("requester_last_name", sa.String(length=100), nullable=False),
        sa.Column("requester_email", sa.String(length=255), nullable=False),
        sa.Column("requester_phone", sa.String(length=50)),
        sa.Column("requester_organization", sa.String(length=255)),
        sa.Column("mailing_address_json", sa.JSON()),
        sa.Column("special_instructions", sa.Text()),
        sa.Column("submitted_at", sa.DateTime()),
        sa.Column("paid_at", sa.DateTime()),
        sa.Column("due_at", sa.DateTime()),
        sa.Column("approved_at", sa.DateTime()),
        sa.Column("delivered_at", sa.DateTime()),
        sa.Column("cancelled_at", sa.DateTime()),
        sa.Column("rejected_at", sa.DateTime()),
        sa.Column("total_amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("current_quote_id", sa.String(length=36), sa.ForeignKey("quotes.id")),
        sa.Column("current_draft_id", sa.String(length=36), sa.ForeignKey("letter_drafts.id")),
        sa.Column("final_letter_version_id", sa.String(length=36), sa.ForeignKey("letter_versions.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_foreign_key(
        "fk_quotes_request_id_requests",
        "quotes",
        "requests",
        ["request_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_letter_drafts_request_id_requests",
        "letter_drafts",
        "requests",
        ["request_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_letter_versions_request_id_requests",
        "letter_versions",
        "requests",
        ["request_id"],
        ["id"],
    )
    op.create_table(
        "request_status_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("request_id", sa.String(length=36), sa.ForeignKey("requests.id"), nullable=False),
        sa.Column("from_status", sa.String(length=50)),
        sa.Column("to_status", sa.String(length=50), nullable=False),
        sa.Column("reason_code", sa.String(length=100)),
        sa.Column("reason_text", sa.Text()),
        sa.Column("acted_by_user_id", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "request_assignments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("request_id", sa.String(length=36), sa.ForeignKey("requests.id"), nullable=False),
        sa.Column("assigned_to_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_by_user_id", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("assignment_reason", sa.Text()),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "request_notes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("request_id", sa.String(length=36), sa.ForeignKey("requests.id"), nullable=False),
        sa.Column("author_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note_type", sa.String(length=50), nullable=False),
        sa.Column("visibility", sa.String(length=50), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "fee_schedule_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("fee_schedule_id", sa.String(length=36), sa.ForeignKey("fee_schedules.id"), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("fee_type", sa.String(length=50), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("applies_to_letter_type", sa.String(length=50)),
        sa.Column("applies_to_processing_type", sa.String(length=50)),
        sa.Column("applies_to_delivery_method", sa.String(length=50)),
        sa.Column("tax_mode", sa.String(length=50)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("request_id", sa.String(length=36), sa.ForeignKey("requests.id"), nullable=False),
        sa.Column("quote_id", sa.String(length=36), sa.ForeignKey("quotes.id"), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=255)),
        sa.Column("provider_checkout_id", sa.String(length=255)),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("paid_at", sa.DateTime()),
        sa.Column("failure_code", sa.String(length=100)),
        sa.Column("failure_message", sa.Text()),
        sa.Column("receipt_url", sa.String(length=1000)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "payment_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("payment_id", sa.String(length=36), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("processed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("provider_event_id", name="uq_payment_events_provider_event_id"),
    )
    op.create_table(
        "deliveries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("request_id", sa.String(length=36), sa.ForeignKey("requests.id"), nullable=False),
        sa.Column("letter_version_id", sa.String(length=36), sa.ForeignKey("letter_versions.id"), nullable=False),
        sa.Column("delivery_method", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("destination", sa.String(length=1000), nullable=False),
        sa.Column("provider_reference", sa.String(length=255)),
        sa.Column("delivered_at", sa.DateTime()),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "email_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("request_id", sa.String(length=36), sa.ForeignKey("requests.id")),
        sa.Column("template_id", sa.String(length=36), sa.ForeignKey("email_templates.id")),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("subject_rendered", sa.Text(), nullable=False),
        sa.Column("body_rendered", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=100)),
        sa.Column("provider_message_id", sa.String(length=255)),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("sent_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("actor_user_id", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("before_json", sa.JSON()),
        sa.Column("after_json", sa.JSON()),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("ip_address", sa.String(length=64)),
        sa.Column("user_agent", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("email_events")
    op.drop_table("deliveries")
    op.drop_table("payment_events")
    op.drop_table("payments")
    op.drop_table("fee_schedule_items")
    op.drop_table("request_notes")
    op.drop_table("request_assignments")
    op.drop_table("request_status_events")
    op.drop_constraint("fk_letter_versions_request_id_requests", "letter_versions", type_="foreignkey")
    op.drop_constraint("fk_letter_drafts_request_id_requests", "letter_drafts", type_="foreignkey")
    op.drop_constraint("fk_quotes_request_id_requests", "quotes", type_="foreignkey")
    op.drop_table("requests")
    op.drop_table("letter_versions")
    op.drop_table("letter_drafts")
    op.drop_table("quotes")
    op.drop_table("email_templates")
    op.drop_table("letter_templates")
    op.drop_table("fee_schedules")
    op.drop_table("property_snapshots")
    op.drop_index("ix_properties_jurisdiction_group_id", table_name="properties")
    op.drop_index("ix_properties_jurisdiction_apn", table_name="properties")
    op.drop_table("properties")
    op.drop_table("sessions")
    op.drop_table("user_roles")
    op.drop_table("jurisdictions")
    op.drop_table("roles")
    op.drop_table("users")
