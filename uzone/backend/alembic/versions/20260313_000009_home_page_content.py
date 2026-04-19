"""Add jurisdiction home page content storage."""

from alembic import op
import sqlalchemy as sa


revision = "20260313_000009"
down_revision = "20260313_000008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shared_jurisdiction_home_page_content",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("jurisdiction_id", sa.String(length=36), nullable=False),
        sa.Column("hero_json", sa.JSON(), nullable=False),
        sa.Column("services_json", sa.JSON(), nullable=False),
        sa.Column("about_json", sa.JSON(), nullable=False),
        sa.Column("faq_json", sa.JSON(), nullable=False),
        sa.Column("contact_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["jurisdiction_id"], ["shared_jurisdictions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jurisdiction_id"),
    )


def downgrade() -> None:
    op.drop_table("shared_jurisdiction_home_page_content")
