"""Tests for assistant guardrail turn contract schema."""

from __future__ import annotations

from app.schemas.assistant_guardrails import AssistantTurnContract


def test_assistant_turn_contract_accepts_valid_payload() -> None:
    payload = AssistantTurnContract(
        intent_type="specific_address",
        jurisdiction_status="in_jurisdiction",
        needs_clarification=False,
        clarification_type="none",
        policy_decision={
            "decision": "allow",
            "reason_code": "in_scope",
            "reason": "Allowed",
        },
        confidence=0.91,
    )
    assert payload.intent_type == "specific_address"
    assert payload.policy_decision.decision == "allow"


def test_assistant_turn_contract_accepts_address_confirmation_state() -> None:
    payload = AssistantTurnContract(
        intent_type="specific_address",
        jurisdiction_status="needs_confirmation",
        needs_clarification=True,
        clarification_type="address_confirmation",
        policy_decision={
            "decision": "clarify",
            "reason_code": "resolved_address_differs",
            "reason": "The resolved parcel differs from the requested address.",
        },
        confidence=0.95,
    )
    assert payload.jurisdiction_status == "needs_confirmation"
    assert payload.clarification_type == "address_confirmation"
