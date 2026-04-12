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
