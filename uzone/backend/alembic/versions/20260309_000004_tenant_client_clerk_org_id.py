"""Add Clerk organization ID mapping to tenant clients."""

from alembic import op
import sqlalchemy as sa


revision = "20260309_000004"
down_revision = "20260308_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shared_tenant_clients", sa.Column("clerk_organization_id", sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        "uq_tenant_clients_clerk_organization_id",
        "shared_tenant_clients",
        ["clerk_organization_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_tenant_clients_clerk_organization_id", "shared_tenant_clients", type_="unique")
    op.drop_column("shared_tenant_clients", "clerk_organization_id")
