"""Prefix tables by application ownership.

Revision ID: 20260419_000013
Revises: 20260414_000012
Create Date: 2026-04-19 00:13:00.000000
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260419_000013"
down_revision = "20260414_000012"
branch_labels = None
depends_on = None


RENAMES = [
    ("users", "shared_users", None),
    ("roles", "shared_roles", None),
    ("user_roles", "shared_user_roles", None),
    ("sessions", "shared_sessions", None),
    ("jurisdictions", "shared_jurisdictions", None),
    ("tenant_clients", "shared_tenant_clients", None),
    ("tenant_domains", "shared_tenant_domains", None),
    ("platform_settings", "shared_platform_settings", None),
    ("assistant_message_feedback", "agentic_assistant_message_feedback", None),
    ("assistant_turn_events", "agentic_assistant_turn_events", None),
    ("assistant_run_telemetry", "agentic_assistant_run_telemetry", None),
    ("zoning_code_ingestion_runs", "agentic_zoning_code_ingestion_runs", None),
    ("zoning_code_documents", "agentic_zoning_code_documents", None),
    ("zoning_code_sections", "agentic_zoning_code_sections", None),
    ("properties", "shared_properties", None),
    ("property_snapshots", "shared_property_snapshots", None),
    ("requests", "letters_requests", None),
    ("request_status_events", "letters_request_status_events", None),
    ("request_assignments", "letters_request_assignments", None),
    ("request_notes", "letters_request_notes", None),
    ("fee_schedules", "letters_fee_schedules", None),
    ("fee_schedule_items", "letters_fee_schedule_items", None),
    ("quotes", "letters_quotes", None),
    ("payments", "letters_payments", None),
    ("payment_events", "letters_payment_events", None),
    ("letter_templates", "letters_letter_templates", None),
    ("letter_drafts", "letters_letter_drafts", None),
    ("letter_versions", "letters_letter_versions", None),
    ("deliveries", "letters_deliveries", None),
    ("email_templates", "shared_email_templates", None),
    ("jurisdiction_home_page_content", "shared_jurisdiction_home_page_content", None),
    ("email_events", "shared_email_events", None),
    ("audit_log", "shared_audit_log", None),
]


VECTOR_SCHEMA = "ai"
VECTOR_TABLE_OLD = "customer_zoning_chunks"
VECTOR_TABLE_NEW = "agentic_customer_zoning_chunks"


def upgrade() -> None:
    bind = op.get_bind()
    for old_name, new_name, schema in RENAMES:
        inspector = inspect(bind)
        if inspector.has_table(new_name, schema=schema):
            continue
        if inspector.has_table(old_name, schema=schema):
            op.rename_table(old_name, new_name, schema=schema)

    inspector = inspect(bind)
    if inspector.has_table(VECTOR_TABLE_OLD, schema=VECTOR_SCHEMA) and not inspector.has_table(
        VECTOR_TABLE_NEW,
        schema=VECTOR_SCHEMA,
    ):
        op.execute(
            f"ALTER TABLE {VECTOR_SCHEMA}.{VECTOR_TABLE_OLD} RENAME TO {VECTOR_TABLE_NEW}"
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table(VECTOR_TABLE_NEW, schema=VECTOR_SCHEMA) and not inspector.has_table(
        VECTOR_TABLE_OLD,
        schema=VECTOR_SCHEMA,
    ):
        op.execute(
            f"ALTER TABLE {VECTOR_SCHEMA}.{VECTOR_TABLE_NEW} RENAME TO {VECTOR_TABLE_OLD}"
        )

    for old_name, new_name, schema in reversed(RENAMES):
        inspector = inspect(bind)
        if inspector.has_table(old_name, schema=schema):
            continue
        if inspector.has_table(new_name, schema=schema):
            op.rename_table(new_name, old_name, schema=schema)
