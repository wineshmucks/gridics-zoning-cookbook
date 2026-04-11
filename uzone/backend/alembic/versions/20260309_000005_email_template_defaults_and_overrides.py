"""Add Gridics default email templates and tenant overrides."""

from alembic import op
import sqlalchemy as sa


revision = "20260309_000005"
down_revision = "20260309_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("email_templates", sa.Column("tenant_client_id", sa.String(length=36), nullable=True))
    op.add_column("email_templates", sa.Column("owner_organization_id", sa.String(length=255), nullable=True))
    op.add_column("email_templates", sa.Column("base_template_id", sa.String(length=36), nullable=True))
    op.add_column("email_templates", sa.Column("trigger_state", sa.String(length=100), nullable=True))
    op.add_column("email_templates", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "email_templates",
        sa.Column("category", sa.String(length=100), nullable=False, server_default="request_updates"),
    )
    op.add_column(
        "email_templates",
        sa.Column("is_system_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_foreign_key(
        "fk_email_templates_tenant_client_id",
        "email_templates",
        "tenant_clients",
        ["tenant_client_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_email_templates_base_template_id",
        "email_templates",
        "email_templates",
        ["base_template_id"],
        ["id"],
    )

    op.execute(
        """
        UPDATE email_templates
        SET
          tenant_client_id = tenant_clients.id,
          owner_organization_id = COALESCE(tenant_clients.clerk_organization_id, tenant_clients.client_id),
          trigger_state = email_templates.code,
          description = email_templates.name
        FROM tenant_clients
        WHERE tenant_clients.jurisdiction_id = email_templates.jurisdiction_id
        """
    )
    op.execute("UPDATE email_templates SET trigger_state = code WHERE trigger_state IS NULL")

    with op.batch_alter_table("email_templates") as batch_op:
        batch_op.alter_column("jurisdiction_id", existing_type=sa.String(length=36), nullable=True)
        batch_op.alter_column("trigger_state", existing_type=sa.String(length=100), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("email_templates") as batch_op:
        batch_op.alter_column("trigger_state", existing_type=sa.String(length=100), nullable=True)
        batch_op.alter_column("jurisdiction_id", existing_type=sa.String(length=36), nullable=False)

    op.drop_constraint("fk_email_templates_base_template_id", "email_templates", type_="foreignkey")
    op.drop_constraint("fk_email_templates_tenant_client_id", "email_templates", type_="foreignkey")
    op.drop_column("email_templates", "is_system_default")
    op.drop_column("email_templates", "category")
    op.drop_column("email_templates", "description")
    op.drop_column("email_templates", "trigger_state")
    op.drop_column("email_templates", "base_template_id")
    op.drop_column("email_templates", "owner_organization_id")
    op.drop_column("email_templates", "tenant_client_id")
