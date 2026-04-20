"""Rename shared email tables into the letters namespace.

Revision ID: 20260420_000016
Revises: 20260420_000015
Create Date: 2026-04-20 00:16:00.000000
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260420_000016"
down_revision = "20260420_000015"
branch_labels = None
depends_on = None


RENAMES = [
    ("shared_email_templates", "letters_email_templates"),
    ("shared_jurisdiction_home_page_content", "letters_jurisdiction_home_page_content"),
    ("shared_email_events", "letters_email_events"),
    ("shared_audit_log", "letters_audit_log"),
]


def upgrade() -> None:
    bind = op.get_bind()
    for old_name, new_name in RENAMES:
        inspector = inspect(bind)
        if inspector.has_table(new_name):
            continue
        if inspector.has_table(old_name):
            op.rename_table(old_name, new_name)


def downgrade() -> None:
    bind = op.get_bind()
    for old_name, new_name in reversed(RENAMES):
        inspector = inspect(bind)
        if inspector.has_table(old_name):
            continue
        if inspector.has_table(new_name):
            op.rename_table(new_name, old_name)
