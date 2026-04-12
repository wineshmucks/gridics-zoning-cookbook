"""Tests for assistant policy guardrails."""

from __future__ import annotations

from app.services.policy_service import classify_scope, evaluate_policy_decision


def test_classify_scope_detects_non_zoning_prompt() -> None:
    decision, reason = classify_scope("What is the weather in Austin today?")
    assert decision == "deny_non_zoning"
    assert "zoning" in reason.lower()


def test_evaluate_policy_decision_allows_general_zoning_when_in_scope() -> None:
    result = evaluate_policy_decision(
        query="What are height limits in downtown zoning districts?",
        question_type="general_zoning",
        tenant_client=None,
    )
    assert result["decision"] == "allow"
    assert result["reason_code"] == "general_zoning_in_scope"


def test_evaluate_policy_decision_requests_scope_clarification_when_ambiguous() -> None:
    result = evaluate_policy_decision(
        query="What can I do there?",
        question_type="general_zoning",
        tenant_client=None,
    )
    assert result["decision"] == "clarify"
    assert result["reason_code"] == "scope_ambiguous"


def test_classify_scope_prefers_agent_decision_when_available(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.policy_service._classify_scope_with_agent",
        lambda query: ("deny_non_zoning", "Model classified as unrelated."),
    )
    decision, reason = classify_scope("Can you recommend a restaurant?")
    assert decision == "deny_non_zoning"
    assert reason == "Model classified as unrelated."
