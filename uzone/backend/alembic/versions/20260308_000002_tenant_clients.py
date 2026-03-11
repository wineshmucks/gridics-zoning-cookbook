"""Add tenant client configuration tables."""

from alembic import op
import sqlalchemy as sa


revision = "20260308_000002"
down_revision = "20260308_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_clients",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("client_id", sa.String(length=100), nullable=False, unique=True),
        sa.Column("jurisdiction_id", sa.String(length=36), sa.ForeignKey("jurisdictions.id")),
        sa.Column("city_name", sa.String(length=255), nullable=False),
        sa.Column("department_name", sa.String(length=255), nullable=False),
        sa.Column("standard_letter_fee_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comprehensive_letter_fee_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expedited_fee_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("support_phone", sa.String(length=50)),
        sa.Column("support_email", sa.String(length=255)),
        sa.Column("contact_address", sa.String(length=255)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("settings_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "tenant_domains",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_client_id", sa.String(length=36), sa.ForeignKey("tenant_clients.id"), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("hostname", name="uq_tenant_domains_hostname"),
    )


def downgrade() -> None:
    op.drop_table("tenant_domains")
    op.drop_table("tenant_clients")
