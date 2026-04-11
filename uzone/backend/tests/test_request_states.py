"""Unit tests for request transition rules."""

import pytest

from app.domain.request_states import ensure_transition_allowed


def test_valid_transition_is_allowed() -> None:
    ensure_transition_allowed("draft", "submitted")


def test_paid_to_review_to_in_progress_transitions_are_allowed() -> None:
    ensure_transition_allowed("paid", "pending_review")
    ensure_transition_allowed("pending_review", "in_progress")


def test_invalid_transition_raises() -> None:
    with pytest.raises(ValueError, match="Invalid request transition"):
        ensure_transition_allowed("draft", "approved")
