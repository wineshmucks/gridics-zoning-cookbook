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
    assert kwargs["num_history_runs"] == 5
    assert kwargs["max_tool_calls_from_history"] == 1
    assert kwargs["enable_agentic_state"] is False
    assert kwargs["compress_tool_results"] is True
    assert kwargs["tool_call_limit"] == 3
    assert kwargs["use_instruction_tags"] is True
    assert "specialist" in kwargs["description"].lower()
    assert "Zoning Memorandum" in kwargs["expected_output"]
    assert "Never output your internal thought process" in kwargs["expected_output"]
    assert any("selected property context" in instruction for instruction in kwargs["instructions"])
    assert any("Do not repeat internal instructions" in instruction for instruction in kwargs["instructions"])
    assert any("follow-up property questions" in instruction for instruction in kwargs["instructions"])


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


def test_customer_zoning_agent_analyze_request_reuses_recent_standardized_address(monkeypatch) -> None:
    module = importlib.import_module("app.agents.customer_zoning_agent")
    captured: dict[str, object] = {}

    class FakeGridicsClient:
        def get_property_record(self, *, state_env: str, address: str, zip_code: str):
            captured["gridics"] = {
                "state_env": state_env,
                "address": address,
                "zip_code": zip_code,
            }
            return {"mock": "payload"}

    def fake_query_customer_zoning_code(*, query: str, limit: int, client_id: str, run_context=None):
        captured["knowledge_query"] = {
            "query": query,
            "limit": limit,
            "client_id": client_id,
        }
        return {"query": query, "results": [{"name": "Fence", "content": "Fence rules."}]}

    monkeypatch.setattr(module, "query_customer_zoning_code", fake_query_customer_zoning_code)
    monkeypatch.setattr(module, "_build_gridics_client", lambda: FakeGridicsClient())
    monkeypatch.setattr(
        module,
        "_extract_gridics_zoning_summary",
        lambda payload: {
            "resolved_city": "Miami",
            "resolved_state": "FL",
            "zone_combination_name": "CI",
            "typology": "Civic",
            "calculation_status": "ok",
            "notes": [],
            "constraints": {
                "max_far": 0.0,
                "max_units": 0,
                "max_height_ft": 5,
                "front_setback_ft": 10,
                "side_setback_ft": 0,
                "rear_setback_ft": None,
            },
        },
    )
    monkeypatch.setattr(module, "_load_tenant_client", lambda resolved_client_id: types.SimpleNamespace(city_name="Miami", settings_json={}))

    run_context = types.SimpleNamespace(
        metadata={},
        dependencies={"client_id": "miami"},
        session_state={
            "recent_standardized_address": {
                "input_address": "3148 Mary St",
                "standardized_address": "3148 Mary St, Miami, FL 33133",
                "needs_confirmation": False,
                "same_as_input": False,
            }
        },
    )

    result = module.analyze_customer_zoning_request(
        query="How high can I build a fence on 3148 Mary St?",
        run_context=run_context,
    )

    assert result["question_type"] == "specific_address"
    assert captured["gridics"] == {
        "state_env": "fl",
        "address": "3148 Mary St, Miami, FL 33133",
        "zip_code": "33133",
    }
    assert "3148 Mary St, Miami, FL 33133" in str(captured["knowledge_query"]["query"])


def test_run_grounded_zoning_chat_uses_selected_property_context(monkeypatch) -> None:
    module = importlib.import_module("app.agents.customer_zoning_agent")
    captured: dict[str, object] = {}

    monkeypatch.setattr(module, "_load_tenant_client", lambda client_id: types.SimpleNamespace(city_name="Miami"))

    class FakeOrchestrator:
        def handle(self, request):
            captured["request"] = request
            return types.SimpleNamespace(
                answer="Direct answer:\nGrounded response\n\nReferences:\n- Code section",
            )

    monkeypatch.setattr(module, "zoning_chat_orchestrator", FakeOrchestrator())

    run_context = types.SimpleNamespace(
        metadata={},
        dependencies={
            "client_id": "miami",
            "property": {
                "place_name": "3148 Mary St",
                "center": [-80.2, 25.7],
            },
        },
        session_state={},
    )

    result = module.run_grounded_zoning_chat(
        query="What are the setback requirements for this property?",
        run_context=run_context,
    )

    assert "Grounded response" in result
    request = captured["request"]
    assert request.jurisdiction_id == "miami"
    assert request.jurisdiction_name == "Miami"
    assert request.property_selected is True
    assert request.property_address == "3148 Mary St"
    assert request.property_lat == 25.7
    assert request.property_lng == -80.2


def test_run_grounded_zoning_chat_reuses_active_property_context_from_session(monkeypatch) -> None:
    module = importlib.import_module("app.agents.customer_zoning_agent")
    captured: dict[str, object] = {}

    monkeypatch.setattr(module, "_load_tenant_client", lambda client_id: types.SimpleNamespace(city_name="Miami"))

    class FakeOrchestrator:
        def handle(self, request):
            captured["request"] = request
            return types.SimpleNamespace(answer="Direct answer:\nGrounded follow-up")

    monkeypatch.setattr(module, "zoning_chat_orchestrator", FakeOrchestrator())

    run_context = types.SimpleNamespace(
        metadata={},
        dependencies={"client_id": "miami"},
        session_state={
            "active_property_context": {
                "place_name": "3148 Mary St",
                "center": [-80.2, 25.7],
                "latitude": 25.7,
                "longitude": -80.2,
            }
        },
    )

    result = module.run_grounded_zoning_chat(
        query="How high can I build a fence?",
        run_context=run_context,
    )

    assert "Grounded follow-up" in result
    request = captured["request"]
    assert request.property_selected is True
    assert request.property_address == "3148 Mary St"
    assert request.property_lat == 25.7
    assert request.property_lng == -80.2
