"""Repair dev auth schema drift and normalize seed emails."""

from alembic import op
import sqlalchemy as sa


revision = "20260308_000003"
down_revision = "20260308_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {column["name"] for column in inspector.get_columns("shared_users")}

    if "clerk_user_id" not in user_columns:
        op.add_column("shared_users", sa.Column("clerk_user_id", sa.String(length=255), nullable=True))
        op.create_unique_constraint("users_clerk_user_id_key", "shared_users", ["clerk_user_id"])

    op.execute(
        sa.text(
            """
            UPDATE shared_users
            SET email = CASE email
                WHEN 'admin@uzone.local' THEN 'admin@uzone.example.com'
                WHEN 'staff@uzone.local' THEN 'staff@uzone.example.com'
                WHEN 'customer@uzone.local' THEN 'customer@uzone.example.com'
                ELSE email
            END
            WHERE email IN (
                'admin@uzone.local',
                'staff@uzone.local',
                'customer@uzone.local'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE shared_jurisdictions
            SET public_contact_email = 'planning@dreamtown.gov'
            WHERE public_contact_email = 'planning@dreamtown.local'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE shared_tenant_clients
            SET support_email = 'planning@dreamtown.gov'
            WHERE support_email = 'planning@dreamtown.local'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE shared_users
            SET email = CASE email
                WHEN 'admin@uzone.example.com' THEN 'admin@uzone.local'
                WHEN 'staff@uzone.example.com' THEN 'staff@uzone.local'
                WHEN 'customer@uzone.example.com' THEN 'customer@uzone.local'
                ELSE email
            END
            WHERE email IN (
                'admin@uzone.example.com',
                'staff@uzone.example.com',
                'customer@uzone.example.com'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE shared_jurisdictions
            SET public_contact_email = 'planning@dreamtown.local'
            WHERE public_contact_email = 'planning@dreamtown.gov'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE shared_tenant_clients
            SET support_email = 'planning@dreamtown.local'
            WHERE support_email = 'planning@dreamtown.gov'
            """
        )
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {column["name"] for column in inspector.get_columns("shared_users")}
    if "clerk_user_id" in user_columns:
        op.drop_constraint("users_clerk_user_id_key", "shared_users", type_="unique")
        op.drop_column("shared_users", "clerk_user_id")
