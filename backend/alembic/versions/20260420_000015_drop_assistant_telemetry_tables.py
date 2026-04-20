"""Drop custom assistant telemetry tables.

Revision ID: 20260420_000015
Revises: 20260419_000014
Create Date: 2026-04-20 00:15:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260420_000015"
down_revision = "20260419_000014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agentic_assistant_run_telemetry")
    op.execute("DROP TABLE IF EXISTS agentic_assistant_turn_events")


def downgrade() -> None:
    op.create_table(
        "agentic_assistant_turn_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_client_id", sa.String(length=36), nullable=True),
        sa.Column("conversation_id", sa.String(length=255), nullable=True),
        sa.Column("message_id", sa.String(length=255), nullable=True),
        sa.Column("run_id", sa.String(length=255), nullable=True),
        sa.Column("agent_id", sa.String(length=100), nullable=True),
        sa.Column("intent_type", sa.String(length=50), nullable=True),
        sa.Column("jurisdiction_status", sa.String(length=50), nullable=True),
        sa.Column("policy_decision", sa.String(length=50), nullable=True),
        sa.Column("reason_code", sa.String(length=100), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_client_id"], ["shared_tenant_clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assistant_turn_events_tenant_created_at",
        "agentic_assistant_turn_events",
        ["tenant_client_id", "created_at"],
    )
    op.create_index(
        "ix_assistant_turn_events_policy_decision",
        "agentic_assistant_turn_events",
        ["policy_decision"],
    )
    op.create_table(
        "agentic_assistant_run_telemetry",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("tenant_client_id", sa.String(length=36), sa.ForeignKey("shared_tenant_clients.id"), nullable=True),
        sa.Column("run_scope", sa.String(length=50), nullable=False),
        sa.Column("agent_id", sa.String(length=100), nullable=True),
        sa.Column("conversation_id", sa.String(length=255), nullable=True),
        sa.Column("message_id", sa.String(length=255), nullable=True),
        sa.Column("run_id", sa.String(length=255), nullable=True),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("model_provider", sa.String(length=100), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("model_id", sa.String(length=255), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost", sa.Numeric(12, 6), nullable=True),
        sa.Column("time_to_first_token", sa.Numeric(12, 4), nullable=True),
        sa.Column("duration_seconds", sa.Numeric(12, 4), nullable=True),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
    )
