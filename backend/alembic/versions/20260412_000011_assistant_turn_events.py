"""Add assistant turn event storage."""

from alembic import op
import sqlalchemy as sa


revision = "20260412_000011"
down_revision = "20260409_000010"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index("ix_assistant_turn_events_policy_decision", table_name="agentic_assistant_turn_events")
    op.drop_index("ix_assistant_turn_events_tenant_created_at", table_name="agentic_assistant_turn_events")
    op.drop_table("agentic_assistant_turn_events")
