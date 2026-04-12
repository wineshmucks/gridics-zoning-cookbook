"""Tests for reusable guardrail response templates."""

from __future__ import annotations

from app.services.response_templates import (
    insufficient_evidence_message,
    jurisdiction_lock_message,
    missing_address_details_message,
)


def test_response_templates_render_expected_text() -> None:
    assert "enough cited zoning evidence" in insufficient_evidence_message(has_property_context=False).lower()
    assert "full property address" in missing_address_details_message().lower()
    assert "locked to Miami" in jurisdiction_lock_message(locked_label="Miami")
