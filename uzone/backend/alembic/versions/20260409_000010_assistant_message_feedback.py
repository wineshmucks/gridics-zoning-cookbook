"""Add assistant message feedback storage."""

from alembic import op
import sqlalchemy as sa


revision = "20260409_000010"
down_revision = "20260313_000009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_message_feedback",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_client_id", sa.String(length=36), nullable=False),
        sa.Column("clerk_user_id", sa.String(length=255), nullable=True),
        sa.Column("agent_id", sa.String(length=100), nullable=False),
        sa.Column("surface", sa.String(length=100), nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("run_id", sa.String(length=255), nullable=True),
        sa.Column("feedback_value", sa.String(length=10), nullable=False),
        sa.Column("message_excerpt", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_client_id"], ["tenant_clients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_client_id",
            "conversation_id",
            "message_id",
            name="uq_assistant_message_feedback_conversation_message",
        ),
    )


def downgrade() -> None:
    op.drop_table("assistant_message_feedback")
