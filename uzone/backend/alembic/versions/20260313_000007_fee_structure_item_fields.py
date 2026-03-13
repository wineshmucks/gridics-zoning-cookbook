"""Add richer fee structure fields to fee schedule items."""

from alembic import op
import sqlalchemy as sa


revision = "20260313_000008"
down_revision = "20260310_000007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fee_schedule_items",
        sa.Column("category", sa.String(length=50), nullable=False, server_default="general"),
    )
    op.add_column("fee_schedule_items", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("fee_schedule_items", sa.Column("charge_unit", sa.String(length=50), nullable=True))
    op.add_column(
        "fee_schedule_items",
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("fee_schedule_items", "display_order")
    op.drop_column("fee_schedule_items", "charge_unit")
    op.drop_column("fee_schedule_items", "description")
    op.drop_column("fee_schedule_items", "category")
