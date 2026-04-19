"""Pytest fixtures for backend route tests."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from .helpers import make_db


@pytest.fixture()
def db_session() -> Session:
    db = make_db()
    try:
        yield db
    finally:
        db.close()
