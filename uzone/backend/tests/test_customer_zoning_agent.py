"""Tests for the customer zoning agent definition."""

from __future__ import annotations

import importlib
import sys
import types


def _reload_customer_zoning_agent_module(monkeypatch):
    captured: dict[str, object] = {}

    def fake_create_agent(**kwargs):
        captured["kwargs"] = kwargs
        return types.SimpleNamespace(**kwargs)

    def fake_build_agent_model(*, model_id_override=None):
        return types.SimpleNamespace(id=model_id_override or "default-model")

    monkeypatch.setattr("app.agents.factory.create_agent", fake_create_agent)
    monkeypatch.setattr("app.agents.factory.build_agent_model", fake_build_agent_model)

    sys.modules.pop("app.agents.customer_zoning_agent", None)
    module = importlib.import_module("app.agents.customer_zoning_agent")
    return module, captured["kwargs"]


def test_customer_zoning_agent_uses_history_not_agentic_state(monkeypatch) -> None:
    module, kwargs = _reload_customer_zoning_agent_module(monkeypatch)

    assert module.customer_zoning_agent.id == "customer-zoning-agent"
    assert kwargs["session_state"] == {"active_property_context": None}
    assert kwargs["add_session_state_to_context"] is True
    assert kwargs["add_history_to_context"] is True
    assert kwargs["num_history_runs"] == 3
    assert kwargs["max_tool_calls_from_history"] == 2
    assert kwargs["enable_agentic_state"] is False
    assert kwargs["compress_tool_results"] is False
    assert kwargs["tool_call_limit"] == 3
    assert kwargs["use_instruction_tags"] is True
    assert "Gridics parcel data" in kwargs["description"]
    assert "specific address" in kwargs["expected_output"]


def test_customer_zoning_agent_model_override_hooks_swap_and_restore(monkeypatch) -> None:
    module, _ = _reload_customer_zoning_agent_module(monkeypatch)
    original_model = types.SimpleNamespace(id="default-model")
    override_model = types.SimpleNamespace(id="override-model")
    run_context = types.SimpleNamespace(metadata={"assistant_model_id": "override-model"})
    agent = types.SimpleNamespace(model=original_model)

    monkeypatch.setattr(module, "build_agent_model", lambda *, model_id_override=None: override_model)

    module._apply_model_override(agent=agent, run_context=run_context)

    assert agent.model is override_model
    assert run_context.metadata[module._MODEL_OVERRIDE_STATE_KEY]["original_model"] is original_model

    module._restore_model_override(agent=agent, run_context=run_context)

    assert agent.model is original_model
    assert module._MODEL_OVERRIDE_STATE_KEY not in run_context.metadata
