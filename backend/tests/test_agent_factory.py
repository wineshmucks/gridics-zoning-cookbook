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
    monkeypatch.setattr(settings, "zoning_agent_llm_model_id", "gemini-2.0-flash-001")
    monkeypatch.setattr(settings, "zoning_agent_llm_api_key", "gemini-key")

    model = build_agent_model()

    assert isinstance(model, FakeGemini)
    assert captured == {"id": "gemini-2.0-flash-001", "api_key": "gemini-key"}
    assert getattr(model, "_uzone_api_key_source") == "env_generic"
    assert getattr(model, "_uzone_api_key_suffix") == "-key"


def test_build_agent_model_rejects_missing_api_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "zoning_agent_llm_model_id", "gemini-2.0-flash-001")
    monkeypatch.setattr(settings, "zoning_agent_llm_api_key", None)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        build_agent_model()


def test_build_agent_model_rejects_non_gemini_provider(monkeypatch) -> None:
    monkeypatch.setattr(settings, "zoning_agent_llm_model_id", "gemini-2.0-flash-001")
    monkeypatch.setattr(settings, "zoning_agent_llm_api_key", "shared-llm-key")

    with pytest.raises(RuntimeError, match="Gemini-only"):
        build_agent_model(provider="openrouter", model_id="nvidia/llama-nemotron-embed-vl-1b-v2:free")


def test_build_agent_model_uses_explicit_key_without_env_fallback(monkeypatch) -> None:
    captured = {}

    class FakeGemini:
        def __init__(self, *, id=None, api_key=None):
            captured["id"] = id
            captured["api_key"] = api_key

    monkeypatch.setattr("agno.models.google.Gemini", FakeGemini)
    monkeypatch.setattr(settings, "zoning_agent_llm_model_id", "gemini-2.0-flash-001")
    monkeypatch.setattr(settings, "zoning_agent_llm_api_key", "env-shared-key")

    model = build_agent_model(
        provider="gemini",
        model_id="gemini-3.1-flash-lite-preview",
        api_key="tenant-db-key",
        allow_env_fallback=False,
    )

    assert isinstance(model, FakeGemini)
    assert captured == {"id": "gemini-3.1-flash-lite-preview", "api_key": "tenant-db-key"}
    assert getattr(model, "_uzone_api_key_source") == "tenant_db"
    assert getattr(model, "_uzone_api_key_suffix") == "-key"


def test_build_agent_model_rejects_missing_explicit_key_when_env_fallback_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "zoning_agent_llm_model_id", "gemini-2.0-flash-001")
    monkeypatch.setattr(settings, "zoning_agent_llm_api_key", "env-shared-key")

    with pytest.raises(RuntimeError, match="Missing API key for the Gemini zoning agent"):
        build_agent_model(
            provider="gemini",
            model_id="gemini-3.1-flash-lite-preview",
            api_key=None,
            allow_env_fallback=False,
        )
