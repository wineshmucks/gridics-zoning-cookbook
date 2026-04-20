"""Tests for assistant policy guardrails."""

from __future__ import annotations

from types import SimpleNamespace

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


def test_evaluate_policy_decision_treats_city_of_prefix_as_same_city() -> None:
    tenant = SimpleNamespace(city_name="City of Miami", settings_json={"state": "fl"})
    result = evaluate_policy_decision(
        query="How high can I build a fence on 3148 Mary St, Miami, FL 33133?",
        question_type="specific_address",
        tenant_client=tenant,
        resolved_city="Miami",
        resolved_state="FL",
    )
    assert result["decision"] == "allow"
    assert result["reason_code"] == "in_scope"


def test_classify_scope_prefers_agent_decision_when_available(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.policy_service._classify_scope_with_agent",
        lambda query: ("deny_non_zoning", "Model classified as unrelated."),
    )
    decision, reason = classify_scope("Can you recommend a restaurant?")
    assert decision == "deny_non_zoning"
    assert reason == "Model classified as unrelated."


def test_scope_guardrail_agent_uses_tenant_assistant_key(monkeypatch) -> None:
    captured = {}

    class FakeGemini:
        def __init__(self, *, id=None, api_key=None):
            captured["id"] = id
            captured["api_key"] = api_key

    def fake_create_agent(**kwargs):
        captured["agent_kwargs"] = kwargs
        return SimpleNamespace(**kwargs)

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("app.services.policy_service.SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(
        "app.services.policy_service.get_platform_assistant_settings_json",
        lambda db: {"assistant_provider_keys": {"gemini": "platform-gemini-key"}},
    )
    monkeypatch.setattr(
        "app.services.policy_service.get_tenant_assistant_settings",
        lambda settings_json: (
            {"gemini": settings_json.get("assistant_provider_keys", {}).get("gemini")},
            {},
        ),
    )
    monkeypatch.setattr("app.agents.factory.create_agent", fake_create_agent)
    monkeypatch.setattr("agno.models.google.Gemini", FakeGemini)
    monkeypatch.setattr("app.services.policy_service._SCOPE_GUARDRAIL_AGENT_CACHE", {})

    result = classify_scope(
        "What are the height limits in this zoning district?",
        tenant_client=SimpleNamespace(settings_json={"assistant_provider_keys": {"gemini": "tenant-gemini-key"}}),
    )

    assert captured["id"] == "gemini-2.5-flash-lite"
    assert captured["api_key"] == "tenant-gemini-key"
    assert captured["agent_kwargs"]["model"]._uzone_api_key_source == "tenant_db"
    assert result[0] in {"allow", "clarify", "deny_non_zoning"}
