"""Tests for assistant eval service metrics."""

from __future__ import annotations

from app.services.assistant_eval_service import evaluate_guardrail_cases


def test_evaluate_guardrail_cases_reports_accuracy() -> None:
    cases = [
        {
            "id": "ok1",
            "category": "policy",
            "query": "What are zoning setbacks?",
            "question_type": "general_zoning",
            "tenant": {"city_name": "Miami", "settings_json": {"state": "fl"}},
            "expected_policy_decision": "allow",
        },
        {
            "id": "ok2",
            "category": "policy",
            "query": "What is the weather in Miami tomorrow?",
            "question_type": "general_zoning",
            "tenant": {"city_name": "Miami", "settings_json": {"state": "fl"}},
            "expected_policy_decision": "deny",
        },
        {
            "id": "ok3",
            "category": "jurisdiction",
            "query": "Can I build at 123 Main St?",
            "question_type": "specific_address",
            "tenant": {"city_name": "Miami", "settings_json": {"state": "fl"}},
            "lookup_ready": False,
            "expected_jurisdiction_status": "unresolved",
        },
    ]
    result = evaluate_guardrail_cases(cases)
    assert result.total_cases == 3
    assert result.policy_accuracy >= 0.5
    assert result.jurisdiction_accuracy == 1.0
    assert result.category_accuracy["policy"] >= 0.5
