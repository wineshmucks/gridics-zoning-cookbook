"""assistant run telemetry

Revision ID: 20260414_000012
Revises: 20260412_000011
Create Date: 2026-04-14 00:12:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260414_000012"
down_revision = "20260412_000011"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_table("agentic_assistant_run_telemetry")
