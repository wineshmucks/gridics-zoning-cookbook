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
    assert module.customer_zoning_team.id == "customer_zoning_team"
    assert kwargs["session_state"] == {"active_property_context": None}
    assert kwargs["add_session_state_to_context"] is True
    assert kwargs["add_history_to_context"] is True
    assert kwargs["num_history_runs"] == 1
    assert kwargs["max_tool_calls_from_history"] == 1
    assert kwargs["enable_agentic_state"] is False
    assert kwargs["compress_tool_results"] is True
    assert kwargs["tool_call_limit"] == 3
    assert kwargs["use_instruction_tags"] is True
    assert "specialist" in kwargs["description"].lower()
    assert "Zoning Memorandum" in kwargs["expected_output"]
    assert "Never output your internal thought process" in kwargs["expected_output"]
    assert any("same_as_input" in instruction for instruction in kwargs["instructions"])
    assert any("Do not repeat internal instructions" in instruction for instruction in kwargs["instructions"])
    assert any("follow-up property questions" in instruction for instruction in kwargs["instructions"])


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


def test_customer_zoning_agent_records_conversation_and_metrics_from_run_context(monkeypatch) -> None:
    module, _ = _reload_customer_zoning_agent_module(monkeypatch)
    captured = {}

    def fake_record_assistant_run_telemetry(*, client_id, payload):
        captured["client_id"] = client_id
        captured["payload"] = payload

    monkeypatch.setattr(module, "record_assistant_run_telemetry", fake_record_assistant_run_telemetry)

    agent = types.SimpleNamespace(id="customer-zoning-agent", model=types.SimpleNamespace())
    run_context = types.SimpleNamespace(
        metadata={},
        dependencies={"client_id": "springfield"},
        session_id="conversation-123",
        message_id="message-456",
        run_id="run-789",
    )
    telemetry_payload = {
        "session_id": "conversation-123",
        "usage": {
            "prompt_tokens": 11,
            "completion_tokens": 9,
            "cost": 0.0125,
            "duration": 3.4,
            "time_to_first_token": 0.6,
        },
    }

    module._record_run_telemetry(agent=agent, run_context=run_context, run_output=telemetry_payload)

    assert captured["client_id"] == "springfield"
    assert captured["payload"]["conversation_id"] == "conversation-123"
    assert captured["payload"]["session_id"] == "conversation-123"
    assert captured["payload"]["message_id"] == "message-456"
    assert captured["payload"]["run_id"] == "run-789"
    assert captured["payload"]["metrics"] == telemetry_payload["usage"]
    assert captured["payload"]["run_output"] == telemetry_payload


def test_customer_zoning_agent_records_telemetry_from_agno_hook_kwargs(monkeypatch) -> None:
    module, _ = _reload_customer_zoning_agent_module(monkeypatch)
    captured = {}

    def fake_record_assistant_run_telemetry(*, client_id, payload):
        captured["client_id"] = client_id
        captured["payload"] = payload

    monkeypatch.setattr(module, "record_assistant_run_telemetry", fake_record_assistant_run_telemetry)

    agent = types.SimpleNamespace(id="customer-zoning-agent", model=types.SimpleNamespace())
    run_output = types.SimpleNamespace(
        metrics=types.SimpleNamespace(
            input_tokens=17,
            output_tokens=23,
            total_tokens=40,
            cost=0.015,
            time_to_first_token=0.4,
            duration=3.2,
        ),
        session_id="conversation-123",
    )

    module._record_run_telemetry(
        agent=agent,
        metadata={"conversation_id": "conversation-123", "message_id": "message-456", "run_id": "run-789"},
        dependencies={"client_id": "springfield"},
        session_state={},
        run_output=run_output,
    )

    assert captured["client_id"] == "springfield"
    assert captured["payload"]["conversation_id"] == "conversation-123"
    assert captured["payload"]["message_id"] == "message-456"
    assert captured["payload"]["run_id"] == "run-789"
    assert captured["payload"]["session_id"] == "conversation-123"
    assert captured["payload"]["metrics"].input_tokens == 17
    assert captured["payload"]["run_output"] is run_output


def test_apply_tenant_assistant_config_ignores_tenant_prompt_overrides(monkeypatch) -> None:
    module = importlib.import_module("app.agents.customer_zoning_agent")
    lead = types.SimpleNamespace(
        id="customer-zoning-agent",
        model=types.SimpleNamespace(id="default-model"),
        instructions=[
            "Lead core instruction.",
            "Treat a short 'yes' reply as confirmation when a pending address-confirmation state exists.",
        ],
        members=[],
    )
    run_context = types.SimpleNamespace(
        metadata={},
        dependencies={"client_id": "miami"},
        session_state={},
    )

    monkeypatch.setattr(
        module,
        "_load_tenant_assistant_config",
        lambda client_id: (
            {"gemini": "tenant-db-key"},
            {},
            {"customer_zoning_team": "Use a polished City of Miami voice."},
        ),
    )

    module._apply_tenant_assistant_config(team=lead, run_context=run_context)

    assert lead.instructions == [
        "Lead core instruction.",
        "Treat a short 'yes' reply as confirmation when a pending address-confirmation state exists.",
    ]


def test_apply_tenant_assistant_config_forces_gemini_provider(monkeypatch) -> None:
    module = importlib.import_module("app.agents.customer_zoning_agent")
    captured = {}
    lead = types.SimpleNamespace(
        id="customer_zoning_team",
        model=types.SimpleNamespace(id="default-model"),
        instructions=[],
        members=[],
    )
    run_context = types.SimpleNamespace(
        metadata={},
        dependencies={"client_id": "miami"},
        session_state={},
    )

    monkeypatch.setattr(
        module,
        "_load_tenant_assistant_config",
        lambda client_id: (
            {"gemini": "tenant-gemini-key"},
            {
                "customer_zoning_team": {
                    "provider": "gemini",
                    "model_id": "gemini-2.0-flash-001",
                    "base_url": "https://example.com",
                }
            },
            {},
        ),
    )

    def fake_build_agent_model(*, provider=None, model_id=None, api_key=None, base_url=None, **kwargs):
        captured.update(
            {
                "provider": provider,
                "model_id": model_id,
                "api_key": api_key,
                "base_url": base_url,
            }
        )
        return types.SimpleNamespace(id=model_id)

    monkeypatch.setattr(module, "build_agent_model", fake_build_agent_model)

    module._apply_tenant_assistant_config(team=lead, run_context=run_context)

    assert captured["provider"] == "gemini"
    assert captured["api_key"] == "tenant-gemini-key"
    assert captured["model_id"] == "gemini-2.5-flash-lite"
