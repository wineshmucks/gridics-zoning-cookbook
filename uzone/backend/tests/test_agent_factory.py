"""Tests for Agno agent compatibility helpers."""

from __future__ import annotations

import pytest

from app.agents.factory import build_agent_model, create_agent
from app.core.config import settings


def test_create_agent_filters_unsupported_kwargs(monkeypatch) -> None:
    captured = {}

    class FakeAgent:
        def __init__(self, *, name=None):
            captured["name"] = name

    monkeypatch.setattr("app.agents.factory.Agent", FakeAgent)

    agent = create_agent(id="customer-zoning-agent", name="Customer Zoning Knowledge Agent")

    assert isinstance(agent, FakeAgent)
    assert captured == {"name": "Customer Zoning Knowledge Agent"}


def test_build_agent_model_uses_gemini(monkeypatch) -> None:
    captured = {}

    class FakeGemini:
        def __init__(self, *, id=None, api_key=None):
            captured["id"] = id
            captured["api_key"] = api_key

    monkeypatch.setattr("agno.models.google.Gemini", FakeGemini)
    monkeypatch.setattr(settings, "zoning_agent_llm_provider", "gemini")
    monkeypatch.setattr(settings, "zoning_agent_llm_model_id", "gemini-2.0-flash-001")
    monkeypatch.setattr(settings, "zoning_agent_llm_api_key", "gemini-key")

    model = build_agent_model()

    assert isinstance(model, FakeGemini)
    assert captured == {"id": "gemini-2.0-flash-001", "api_key": "gemini-key"}


def test_build_agent_model_uses_openrouter_default_base_url(monkeypatch) -> None:
    captured = {}

    class FakeOpenRouter:
        def __init__(self, *, id=None, api_key=None, base_url=None):
            captured["id"] = id
            captured["api_key"] = api_key
            captured["base_url"] = base_url

    monkeypatch.setattr("agno.models.openrouter.OpenRouter", FakeOpenRouter)
    monkeypatch.setattr(settings, "zoning_agent_llm_provider", "openrouter")
    monkeypatch.setattr(settings, "zoning_agent_llm_model_id", "openai/gpt-4.1-mini")
    monkeypatch.setattr(settings, "zoning_agent_llm_api_key", "openrouter-key")
    monkeypatch.setattr(settings, "zoning_agent_llm_base_url", None)

    model = build_agent_model()

    assert isinstance(model, FakeOpenRouter)
    assert captured == {
        "id": "openai/gpt-4.1-mini",
        "api_key": "openrouter-key",
        "base_url": "https://openrouter.ai/api/v1",
    }


def test_build_agent_model_accepts_model_override(monkeypatch) -> None:
    captured = {}

    class FakeOpenRouter:
        def __init__(self, *, id=None, api_key=None, base_url=None):
            captured["id"] = id
            captured["api_key"] = api_key
            captured["base_url"] = base_url

    monkeypatch.setattr("agno.models.openrouter.OpenRouter", FakeOpenRouter)
    monkeypatch.setattr(settings, "zoning_agent_llm_provider", "openrouter")
    monkeypatch.setattr(settings, "zoning_agent_llm_model_id", "default/model")
    monkeypatch.setattr(settings, "zoning_agent_llm_api_key", "openrouter-key")
    monkeypatch.setattr(settings, "zoning_agent_llm_base_url", None)

    model = build_agent_model(model_id_override="override/model")

    assert isinstance(model, FakeOpenRouter)
    assert captured == {
        "id": "override/model",
        "api_key": "openrouter-key",
        "base_url": "https://openrouter.ai/api/v1",
    }


def test_build_agent_model_rejects_missing_api_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "zoning_agent_llm_provider", "gemini")
    monkeypatch.setattr(settings, "zoning_agent_llm_model_id", "gemini-2.0-flash-001")
    monkeypatch.setattr(settings, "zoning_agent_llm_api_key", None)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        build_agent_model()


def test_build_agent_model_uses_groq(monkeypatch) -> None:
    captured = {}

    class FakeGroq:
        def __init__(self, *, id=None, api_key=None):
            captured["id"] = id
            captured["api_key"] = api_key

    monkeypatch.setattr("agno.models.groq.Groq", FakeGroq)
    monkeypatch.setattr(settings, "zoning_agent_llm_provider", "groq")
    monkeypatch.setattr(settings, "zoning_agent_llm_model_id", "llama3-8b-8192")
    monkeypatch.setattr(settings, "zoning_agent_llm_api_key", "groq-key")

    model = build_agent_model()

    assert isinstance(model, FakeGroq)
    assert captured == {"id": "llama3-8b-8192", "api_key": "groq-key"}
