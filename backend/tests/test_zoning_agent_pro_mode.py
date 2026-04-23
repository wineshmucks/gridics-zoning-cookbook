"""Tests for pro-mode zoning model selection."""

from __future__ import annotations

import importlib
import sys
import types


def _reload_zoning_agent_module(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-gemini-key")
    sys.modules.pop("app.agents.zoning_agent", None)
    return importlib.import_module("app.agents.zoning_agent")


def test_customer_zoning_agent_uses_standard_model_by_default(monkeypatch) -> None:
    module = _reload_zoning_agent_module(monkeypatch)
    captured: dict[str, object] = {}

    class FakeGemini:
        def __init__(self, *, id=None, api_key=None):
            self.id = id
            self.api_key = api_key

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["model_id"] = getattr(kwargs["model"], "id", None)
            captured["api_key"] = getattr(kwargs["model"], "api_key", None)
            captured["kwargs"] = kwargs
            self.__dict__.update(kwargs)

    monkeypatch.setattr(module, "Gemini", FakeGemini)
    monkeypatch.setattr(module, "Agent", FakeAgent)

    agent = module.build_customer_zoning_agent()

    assert agent.id == "customer-zoning-agent"
    assert captured["model_id"] == "gemini-2.5-flash-lite"
    assert captured["api_key"] == "test-gemini-key"


def test_customer_zoning_agent_switches_to_pro_mode(monkeypatch) -> None:
    module = _reload_zoning_agent_module(monkeypatch)
    captured: dict[str, object] = {}

    class FakeGemini:
        def __init__(self, *, id=None, api_key=None):
            self.id = id
            self.api_key = api_key

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["model_id"] = getattr(kwargs["model"], "id", None)
            captured["api_key"] = getattr(kwargs["model"], "api_key", None)
            captured["kwargs"] = kwargs
            self.__dict__.update(kwargs)

    monkeypatch.setattr(module, "Gemini", FakeGemini)
    monkeypatch.setattr(module, "Agent", FakeAgent)

    agent = module.build_customer_zoning_agent()
    pre_hook = next(hook for hook in captured["kwargs"]["pre_hooks"] if hook.__name__ == "_apply_customer_zoning_model_pre_hook")

    fake_runtime_agent = types.SimpleNamespace(model=types.SimpleNamespace(id="gemini-2.5-flash-lite"))
    pre_hook(fake_runtime_agent, metadata={"assistant_mode": "pro"})

    assert agent.id == "customer-zoning-agent"
    assert fake_runtime_agent.model.id == "gemini-2.5-pro"
    assert fake_runtime_agent.model.api_key == "test-gemini-key"
