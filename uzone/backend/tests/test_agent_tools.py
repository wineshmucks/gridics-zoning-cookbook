"""Tests for Agno zoning tools."""

from __future__ import annotations

import sys
import types
import json

from app.agents.tools import analyze_customer_zoning_request, query_customer_zoning_code


class DummyTenant:
    client_id = "springfield"


class DummyTenantClient:
    def __init__(self, city_name: str = "Springfield", settings_json: dict[str, object] | None = None) -> None:
        self.city_name = city_name
        self.settings_json = settings_json or {}


class DummyRunContext:
    def __init__(self, dependencies: dict[str, object] | None = None) -> None:
        self.dependencies = dependencies
        self.session_state: dict[str, object] = {}


def test_query_customer_zoning_code_uses_run_context_client_id(monkeypatch) -> None:
    tenant = DummyTenant()
    captured: dict[str, object] = {}

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def scalar(self, statement):
            captured["statement"] = statement
            return tenant

    def fake_query_customer_zoning_knowledge(db, tenant_client, *, query: str, limit: int):
        captured["db"] = db
        captured["tenant_client"] = tenant_client
        captured["query"] = query
        captured["limit"] = limit
        return {"query": query, "results": []}

    session_module = types.ModuleType("app.db.session")
    session_module.SessionLocal = lambda: FakeSession()
    monkeypatch.setitem(sys.modules, "app.db.session", session_module)
    monkeypatch.setattr(
        "app.services.zoning_knowledge_service.query_customer_zoning_knowledge",
        fake_query_customer_zoning_knowledge,
    )

    result = query_customer_zoning_code(
        query="What are the height limits?",
        limit=4,
        run_context=DummyRunContext({"client_id": "springfield"}),
    )

    assert result == {"query": "What are the height limits?", "results": []}
    assert captured["tenant_client"] is tenant
    assert captured["query"] == "What are the height limits?"
    assert captured["limit"] == 4


def test_query_customer_zoning_code_requires_client_id_when_unbound() -> None:
    try:
        query_customer_zoning_code(query="Anything here?")
    except ValueError as exc:
        assert "client_id" in str(exc)
    else:  # pragma: no cover - explicit failure branch
        raise AssertionError("Expected ValueError when no client_id is provided")


def test_analyze_customer_zoning_request_routes_general_questions_to_knowledge(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_query_customer_zoning_code(*, query: str, limit: int, client_id: str, run_context=None):
        captured["query"] = query
        captured["limit"] = limit
        captured["client_id"] = client_id
        return {"query": query, "results": [{"name": "General standard", "content": "General zoning answer"}]}

    monkeypatch.setattr("app.agents.tools.query_customer_zoning_code", fake_query_customer_zoning_code)

    result = analyze_customer_zoning_request(
        query="What are the typical height limits in downtown zones?",
        knowledge_limit=3,
        run_context=DummyRunContext({"client_id": "springfield"}),
    )

    assert result["question_type"] == "general_zoning"
    assert result["assistant_turn"]["intent_type"] == "general_zoning"
    assert result["assistant_turn"]["jurisdiction_status"] == "not_applicable"
    assert "No property address was detected" in str(result["routing_reason"])
    assert result["request_classification"] == {
        "type": "general_zoning",
        "label": "general zoning",
        "reason": "No property address was detected, so the request was handled as a general zoning question.",
    }
    assert result["follow_up_context"] == {
        "context_type": "general_zoning",
        "active_location": None,
        "reuse_for_follow_ups": False,
        "guidance": "Do not assume a property context for follow-up questions unless the user provides a specific address.",
    }
    assert result["knowledge"]["results"][0]["name"] == "General standard"
    assert result["citation_check"]["status"] in {"complete", "missing_citations"}
    assert result["confidence_band"] in {"high_confidence", "medium_confidence", "needs_verification"}
    assert captured == {
        "query": "What are the typical height limits in downtown zones?",
        "limit": 3,
        "client_id": "springfield",
    }


def test_analyze_customer_zoning_request_enriches_address_questions_with_gridics(monkeypatch) -> None:
    gridics_calls: list[dict[str, str]] = []
    knowledge_calls: list[dict[str, object]] = []

    class FakeGridicsClient:
        def get_property_record(self, *, state_env: str, address: str, zip_code: str):
            gridics_calls.append(
                {
                    "state_env": state_env,
                    "address": address,
                    "zip_code": zip_code,
                }
            )
            return {"mock": "payload"}

    def fake_build_gridics_client():
        return FakeGridicsClient()

    def fake_extract_gridics_zoning_summary(payload):
        assert payload == {"mock": "payload"}
        return {
            "zone_combination_name": "R-3 Mixed",
            "typology": "Residential",
            "calculation_status": "ok",
            "notes": ["Overlay review may apply."],
            "constraints": {
                "max_far": 1.5,
                "max_units": 12,
                "max_height_ft": 45,
                "front_setback_ft": None,
                "side_setback_ft": None,
                "rear_setback_ft": None,
            },
        }

    def fake_query_customer_zoning_code(*, query: str, limit: int, client_id: str, run_context=None):
        knowledge_calls.append(
            {
                "query": query,
                "limit": limit,
                "client_id": client_id,
            }
        )
        return {"query": query, "results": [{"name": "R-3 standards", "content": "Applies to R-3."}]}

    monkeypatch.setattr("app.agents.tools._build_gridics_client", fake_build_gridics_client)
    monkeypatch.setattr("app.agents.tools._extract_gridics_zoning_summary", fake_extract_gridics_zoning_summary)
    monkeypatch.setattr("app.agents.tools.query_customer_zoning_code", fake_query_customer_zoning_code)

    result = analyze_customer_zoning_request(
        query="Can I build an ADU at 123 Main Street Apt 4, Springfield, IL 62704?",
        knowledge_limit=4,
        run_context=DummyRunContext({"client_id": "springfield"}),
    )

    assert result["question_type"] == "specific_address"
    assert result["assistant_turn"]["intent_type"] == "specific_address"
    assert result["assistant_turn"]["jurisdiction_status"] == "in_jurisdiction"
    assert result["confidence_band"] in {"high_confidence", "medium_confidence", "needs_verification"}
    assert result["request_classification"] == {
        "type": "specific_address",
        "label": "specific address",
        "reason": "A property address was detected, so the request was enriched with parcel-specific Gridics zoning data.",
    }
    assert result["address_context"] == {
        "address_source": "query",
        "detected_address": "123 Main Street Apt 4, Springfield, IL 62704",
        "standardized_address": "123 Main Street, Springfield, IL 62704",
        "state_env": "il",
        "zip_code": "62704",
    }
    assert result["address_resolution"] == {
        "input_address": "123 Main Street Apt 4, Springfield, IL 62704",
        "standardized_address": "123 Main Street, Springfield, IL 62704",
        "resolved_state_env": "il",
        "resolved_zip_code": "62704",
        "address_source": "query",
        "lookup_ready": True,
    }
    assert result["follow_up_context"] == {
        "context_type": "specific_address",
        "active_location": {
            "standardized_address": "123 Main Street, Springfield, IL 62704",
            "state_env": "il",
            "zip_code": "62704",
            "zone_combination_name": "R-3 Mixed",
            "typology": "Residential",
            "constraints": {
                "max_far": 1.5,
                "max_units": 12,
                "max_height_ft": 45,
                "front_setback_ft": None,
                "side_setback_ft": None,
                "rear_setback_ft": None,
            },
        },
        "reuse_for_follow_ups": True,
        "guidance": "Use this property as the default context for follow-up zoning questions until the user supplies a different address.",
    }
    assert result["gridics"]["zone_combination_name"] == "R-3 Mixed"
    assert result["memo_context"] == {
        "resolved_address": "123 Main Street, Springfield, IL 62704",
        "zone_classification": "R-3 Mixed",
        "typology": "Residential",
        "dimensional_standards": {
            "Max FAR": "1.5",
            "Max Units": "12 units",
            "Max Height": "45 ft",
            "Front Setback": "Not specified",
            "Side Setback": "Not specified",
            "Rear Setback": "Not specified",
        },
        "gridics_system_notes": ["Overlay review may apply."],
        "agent_directives": (
            "Base the memorandum on the structured zoning summary and customer-scoped knowledge. "
            "If parcel-specific Gridics context and broader code references do not align cleanly, explain the discrepancy "
            "professionally and avoid overstating certainty."
        ),
    }
    assert gridics_calls == [
        {
            "state_env": "il",
            "address": "123 Main Street",
            "zip_code": "62704",
        }
    ]
    assert knowledge_calls == [
        {
            "query": (
                "Can I build an ADU at 123 Main Street Apt 4, Springfield, IL 62704?\n"
                "Address: 123 Main Street, Springfield, IL 62704\n"
                "Gridics zone: R-3 Mixed\n"
                "Gridics typology: Residential\n"
                "Explain this zoning district in plain English for this property, including what is typically allowed here, "
                "what approval or reference sections matter most, and any numeric development standards that apply.\n"
                "Observed constraints: max FAR=1.5, max units=12, max height ft=45"
            ),
            "limit": 4,
            "client_id": "springfield",
        },
    ]


def test_analyze_customer_zoning_request_requires_confirmation_when_gridics_resolves_different_parcel(monkeypatch) -> None:
    knowledge_called = False
    run_context = DummyRunContext({"client_id": "springfield"})

    class FakeGridicsClient:
        def get_property_record(self, *, state_env: str, address: str, zip_code: str):
            return {"mock": "payload"}

    def fake_build_gridics_client():
        return FakeGridicsClient()

    def fake_extract_gridics_zoning_summary(payload):
        assert payload == {"mock": "payload"}
        return {
            "resolved_address": "4729 NE MIAMI PL",
            "resolved_city": "Miami",
            "resolved_state": "FL",
            "zone_combination_name": "T3-L",
            "typology": "Residential",
            "calculation_status": "ok",
            "notes": [],
            "constraints": {
                "max_far": 0.8,
                "max_units": 1,
                "max_height_ft": 25,
                "front_setback_ft": 20,
                "side_setback_ft": 5,
                "rear_setback_ft": 20,
            },
        }

    def fake_query_customer_zoning_code(*args, **kwargs):
        nonlocal knowledge_called
        knowledge_called = True
        raise AssertionError("Knowledge lookup should not run before parcel confirmation")

    monkeypatch.setattr("app.agents.tools._build_gridics_client", fake_build_gridics_client)
    monkeypatch.setattr("app.agents.tools._extract_gridics_zoning_summary", fake_extract_gridics_zoning_summary)
    monkeypatch.setattr("app.agents.tools.query_customer_zoning_code", fake_query_customer_zoning_code)

    result = analyze_customer_zoning_request(
        query="What can I build at 2060 Biscayne Blvd, Miami, FL 33137?",
        run_context=run_context,
    )

    assert knowledge_called is False
    assert result["question_type"] == "specific_address"
    assert result["assistant_turn"]["intent_type"] == "specific_address"
    assert result["assistant_turn"]["needs_clarification"] is True
    assert result["response_guardrail"]["needs_confirmation"] is True
    assert result["response_guardrail"]["requested_address"] == "2060 Biscayne Blvd, Miami, FL 33137"
    assert result["response_guardrail"]["resolved_address"] == "4729 NE MIAMI PL"
    assert result["response_guardrail"]["message"] == (
        "The address you entered appears to resolve to 4729 NE MIAMI PL, not 2060 Biscayne Blvd, Miami, FL 33137. "
        "Please confirm the address you want me to use before I continue."
    )
    assert result["response_guardrail"]["assistant_turn"]["jurisdiction_status"] == "needs_confirmation"
    assert result["response_guardrail"]["assistant_turn"]["clarification_type"] == "address_confirmation"
    assert result["response_guardrail"]["assistant_turn"]["needs_clarification"] is True
    assert result["request_classification"]["reason"] == (
        "Gridics resolved a different parcel than the user requested, so confirmation is required."
    )
    assert run_context.session_state["pending_property_confirmation"] == {
        "requested_address": "2060 Biscayne Blvd, Miami, FL 33137",
        "resolved_address": "4729 NE MIAMI PL",
        "state_env": "fl",
        "zip_code": "33137",
    }


def test_analyze_customer_zoning_request_uses_pending_confirmation_when_user_confirms_resolved_parcel(
    monkeypatch,
) -> None:
    gridics_calls: list[dict[str, str]] = []
    knowledge_calls: list[str] = []
    run_context = DummyRunContext({"client_id": "springfield"})

    class FakeGridicsClient:
        def get_property_record(self, *, state_env: str, address: str, zip_code: str):
            gridics_calls.append(
                {
                    "state_env": state_env,
                    "address": address,
                    "zip_code": zip_code,
                }
            )
            return {"mock": "payload"}

    def fake_build_gridics_client():
        return FakeGridicsClient()

    def fake_extract_gridics_zoning_summary(payload):
        assert payload == {"mock": "payload"}
        return {
            "resolved_address": "4729 NE MIAMI PL",
            "resolved_city": "Miami",
            "resolved_state": "FL",
            "zone_combination_name": "T3-L",
            "typology": "Residential",
            "calculation_status": "ok",
            "notes": [],
            "constraints": {
                "max_far": 0.8,
                "max_units": 1,
                "max_height_ft": 25,
                "front_setback_ft": 20,
                "side_setback_ft": 5,
                "rear_setback_ft": 20,
            },
        }

    def fake_query_customer_zoning_code(*, query: str, limit: int, client_id: str, run_context=None):
        knowledge_calls.append(query)
        return {"query": query, "results": [{"name": "Parcel standards", "content": "Parcel-specific answer."}]}

    monkeypatch.setattr("app.agents.tools._build_gridics_client", fake_build_gridics_client)
    monkeypatch.setattr("app.agents.tools._extract_gridics_zoning_summary", fake_extract_gridics_zoning_summary)
    monkeypatch.setattr("app.agents.tools.query_customer_zoning_code", fake_query_customer_zoning_code)
    monkeypatch.setattr(
        "app.agents.tools.grounding_verdict",
        lambda evidence_pack, min_refs=1: {"answer_ready": True, "evidence_count": 1},
    )
    monkeypatch.setattr(
        "app.agents.tools.citation_completeness_report",
        lambda **kwargs: {"is_complete": True, "missing_sources": []},
    )

    first_result = analyze_customer_zoning_request(
        query="What can I build at 2060 Biscayne Blvd, Miami, FL 33137?",
        run_context=run_context,
    )

    second_result = analyze_customer_zoning_request(
        query="4729 NE Miami Pl",
        run_context=run_context,
    )

    assert first_result["response_guardrail"]["needs_confirmation"] is True
    assert second_result["question_type"] == "specific_address"
    assert second_result["address_context"] == {
        "address_source": "confirmation",
        "detected_address": "4729 NE MIAMI PL",
        "standardized_address": "4729 NE MIAMI PL",
        "state_env": "fl",
        "zip_code": "33137",
    }
    assert second_result["address_resolution"] == {
        "input_address": "4729 NE MIAMI PL",
        "standardized_address": "4729 NE MIAMI PL",
        "resolved_state_env": "fl",
        "resolved_zip_code": "33137",
        "address_source": "confirmation",
        "lookup_ready": True,
    }
    assert second_result["assistant_turn"]["needs_clarification"] is False
    assert second_result["follow_up_context"]["active_location"]["standardized_address"] == "4729 NE MIAMI PL"
    assert gridics_calls == [
        {
            "state_env": "fl",
            "address": "2060 Biscayne Blvd",
            "zip_code": "33137",
        },
        {
            "state_env": "fl",
            "address": "4729 NE MIAMI PL",
            "zip_code": "33137",
        },
    ]
    assert knowledge_calls
    assert "pending_property_confirmation" not in run_context.session_state


def test_analyze_customer_zoning_request_uses_pending_confirmation_for_affirmative_reply(monkeypatch) -> None:
    gridics_calls: list[dict[str, str]] = []
    knowledge_calls: list[str] = []
    run_context = DummyRunContext({"client_id": "springfield"})
    run_context.session_state["pending_property_confirmation"] = {
        "requested_address": "2060 Biscayne Blvd, Miami, FL 33137",
        "resolved_address": "4729 NE MIAMI PL",
        "state_env": "fl",
        "zip_code": "33137",
    }

    class FakeGridicsClient:
        def get_property_record(self, *, state_env: str, address: str, zip_code: str):
            gridics_calls.append(
                {
                    "state_env": state_env,
                    "address": address,
                    "zip_code": zip_code,
                }
            )
            return {"mock": "payload"}

    def fake_build_gridics_client():
        return FakeGridicsClient()

    def fake_extract_gridics_zoning_summary(payload):
        assert payload == {"mock": "payload"}
        return {
            "resolved_address": "4729 NE MIAMI PL",
            "resolved_city": "Miami",
            "resolved_state": "FL",
            "zone_combination_name": "T3-L",
            "typology": "Residential",
            "calculation_status": "ok",
            "notes": [],
            "constraints": {
                "max_far": 0.8,
                "max_units": 1,
                "max_height_ft": 25,
                "front_setback_ft": 20,
                "side_setback_ft": 5,
                "rear_setback_ft": 20,
            },
        }

    def fake_query_customer_zoning_code(*, query: str, limit: int, client_id: str, run_context=None):
        knowledge_calls.append(query)
        return {"query": query, "results": [{"name": "Parcel standards", "content": "Parcel-specific answer."}]}

    monkeypatch.setattr("app.agents.tools._build_gridics_client", fake_build_gridics_client)
    monkeypatch.setattr("app.agents.tools._extract_gridics_zoning_summary", fake_extract_gridics_zoning_summary)
    monkeypatch.setattr("app.agents.tools.query_customer_zoning_code", fake_query_customer_zoning_code)
    monkeypatch.setattr(
        "app.agents.tools.grounding_verdict",
        lambda evidence_pack, min_refs=1: {"answer_ready": True, "evidence_count": 1},
    )
    monkeypatch.setattr(
        "app.agents.tools.citation_completeness_report",
        lambda **kwargs: {"is_complete": True, "missing_sources": []},
    )

    result = analyze_customer_zoning_request(
        query="yes continue",
        run_context=run_context,
    )

    assert result["question_type"] == "specific_address"
    assert result["address_context"] == {
        "address_source": "confirmation",
        "detected_address": "4729 NE MIAMI PL",
        "standardized_address": "4729 NE MIAMI PL",
        "state_env": "fl",
        "zip_code": "33137",
    }
    assert result["assistant_turn"]["needs_clarification"] is False
    assert result["follow_up_context"]["active_location"]["standardized_address"] == "4729 NE MIAMI PL"
    assert gridics_calls == [
        {
            "state_env": "fl",
            "address": "4729 NE MIAMI PL",
            "zip_code": "33137",
        }
    ]
    assert knowledge_calls
    assert "pending_property_confirmation" not in run_context.session_state


def test_analyze_customer_zoning_request_keeps_pending_confirmation_open_when_reply_is_ambiguous(
    monkeypatch,
) -> None:
    gridics_called = False
    run_context = DummyRunContext({"client_id": "springfield"})
    run_context.session_state["pending_property_confirmation"] = {
        "requested_address": "2060 Biscayne Blvd, Miami, FL 33137",
        "resolved_address": "4729 NE MIAMI PL",
        "state_env": "fl",
        "zip_code": "33137",
    }

    def fake_classify_pending_property_confirmation_response(*, query: str, pending_context: dict[str, object], tenant_client=None):
        return {
            "decision": "clarify",
            "reason": "Ambiguous confirmation response.",
            "confidence": 0.4,
            "clarification_prompt": "Please confirm that I should use 4729 NE MIAMI PL or give me the correct address.",
        }

    def fail_if_gridics_called(*args, **kwargs):
        nonlocal gridics_called
        gridics_called = True
        raise AssertionError("Gridics should not be called while confirmation is still pending")

    monkeypatch.setattr("app.agents.tools.classify_pending_property_confirmation_response", fake_classify_pending_property_confirmation_response)
    monkeypatch.setattr("app.agents.tools._build_gridics_client", fail_if_gridics_called)

    result = analyze_customer_zoning_request(
        query="not sure",
        run_context=run_context,
    )

    assert gridics_called is False
    assert result["question_type"] == "specific_address"
    assert result["response_guardrail"]["needs_confirmation"] is True
    assert result["response_guardrail"]["message"] == "Please confirm that I should use 4729 NE MIAMI PL or give me the correct address."
    assert result["assistant_turn"]["needs_clarification"] is True
    assert result["clarification_prompt"] == "Please confirm that I should use 4729 NE MIAMI PL or give me the correct address."
    assert run_context.session_state["pending_property_confirmation"] == {
        "requested_address": "2060 Biscayne Blvd, Miami, FL 33137",
        "resolved_address": "4729 NE MIAMI PL",
        "state_env": "fl",
        "zip_code": "33137",
    }


def test_analyze_customer_zoning_request_requests_full_address_when_location_details_missing(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("Gridics should not be called when state or ZIP is missing")

    monkeypatch.setattr("app.agents.tools._build_gridics_client", fail_if_called)

    result = analyze_customer_zoning_request(
        query="What can I build at 123 Main Street?",
        run_context=DummyRunContext({"client_id": "springfield"}),
    )

    assert result["question_type"] == "specific_address"
    assert result["needs_address_clarification"] is True
    assert result["request_classification"] == {
        "type": "specific_address",
        "label": "specific address",
        "reason": "A property address was detected, but it was missing enough location detail for a Gridics lookup.",
    }
    assert result["address_context"]["standardized_address"] == "123 Main Street"
    assert result["address_context"]["state_env"] is None
    assert result["address_context"]["zip_code"] is None
    assert result["address_resolution"] == {
        "input_address": "123 Main Street",
        "standardized_address": "123 Main Street",
        "resolved_state_env": None,
        "resolved_zip_code": None,
        "address_source": "query",
        "lookup_ready": False,
    }
    assert result["follow_up_context"] == {
        "context_type": "specific_address",
        "active_location": {
            "standardized_address": "123 Main Street",
            "state_env": None,
            "zip_code": None,
            "zone_combination_name": None,
            "typology": None,
            "constraints": None,
        },
        "reuse_for_follow_ups": True,
        "guidance": "Use this property as the default context for follow-up zoning questions until the user supplies a different address.",
    }


def test_analyze_customer_zoning_request_accepts_integer_zip_code(monkeypatch) -> None:
    gridics_calls: list[dict[str, str]] = []

    class FakeGridicsClient:
        def get_property_record(self, *, state_env: str, address: str, zip_code: str):
            gridics_calls.append(
                {
                    "state_env": state_env,
                    "address": address,
                    "zip_code": zip_code,
                }
            )
            return {"mock": "payload"}

    def fake_build_gridics_client():
        return FakeGridicsClient()

    def fake_extract_gridics_zoning_summary(payload):
        assert payload == {"mock": "payload"}
        return {
            "zone_combination_name": "R-3 Mixed",
            "typology": "Residential",
            "calculation_status": "ok",
            "notes": [],
            "constraints": {
                "max_far": 1.0,
                "max_units": 2,
                "max_height_ft": 35,
                "front_setback_ft": 10,
                "side_setback_ft": 5,
                "rear_setback_ft": 20,
            },
        }

    def fake_query_customer_zoning_code(*, query: str, limit: int, client_id: str, run_context=None):
        return {"query": query, "results": []}

    monkeypatch.setattr("app.agents.tools._build_gridics_client", fake_build_gridics_client)
    monkeypatch.setattr("app.agents.tools._extract_gridics_zoning_summary", fake_extract_gridics_zoning_summary)
    monkeypatch.setattr("app.agents.tools.query_customer_zoning_code", fake_query_customer_zoning_code)

    result = analyze_customer_zoning_request(
        query="What can I build here?",
        address="123 Main Street, Miami, FL",
        state_env="fl",
        zip_code=33138,
        run_context=DummyRunContext({"client_id": "springfield"}),
    )

    assert result["address_context"]["zip_code"] == "33138"
    assert result["address_resolution"]["resolved_zip_code"] == "33138"
    assert gridics_calls == [
        {
            "state_env": "fl",
            "address": "123 Main Street, Miami, FL",
            "zip_code": "33138",
        }
    ]


def test_analyze_customer_zoning_request_runs_constraints_lookup_only_when_primary_is_empty(monkeypatch) -> None:
    knowledge_calls: list[str] = []

    class FakeGridicsClient:
        call_log: list[dict[str, object]] = []

        def get_property_record(self, *, state_env: str, address: str, zip_code: str):
            return {"mock": "payload"}

    def fake_build_gridics_client():
        return FakeGridicsClient()

    def fake_extract_gridics_zoning_summary(payload):
        assert payload == {"mock": "payload"}
        return {
            "zone_combination_name": "RU-1",
            "typology": "Residential",
            "calculation_status": "ok",
            "notes": [],
            "constraints": {
                "max_far": None,
                "max_units": None,
                "max_height_ft": None,
                "front_setback_ft": None,
                "side_setback_ft": None,
                "rear_setback_ft": None,
            },
        }

    def fake_query_customer_zoning_code(*, query: str, limit: int, client_id: str, run_context=None):
        knowledge_calls.append(query)
        if len(knowledge_calls) == 1:
            return {"query": query, "results": []}
        return {"query": query, "results": [{"name": "Numeric standards", "content": "Height 35 feet."}]}

    monkeypatch.setattr("app.agents.tools._build_gridics_client", fake_build_gridics_client)
    monkeypatch.setattr("app.agents.tools._extract_gridics_zoning_summary", fake_extract_gridics_zoning_summary)
    monkeypatch.setattr("app.agents.tools.query_customer_zoning_code", fake_query_customer_zoning_code)

    result = analyze_customer_zoning_request(
        query="Tell me about 1101 NE 90 St, Miami, FL 33138",
        run_context=DummyRunContext({"client_id": "springfield"}),
    )

    assert len(knowledge_calls) == 2
    assert "Explain this zoning district in plain English" in knowledge_calls[0]
    assert "Find numeric development standards and dimensional controls" in knowledge_calls[1]
    assert result["constraints_knowledge"]["results"][0]["content"] == "Height 35 feet."


def test_analyze_customer_zoning_request_retries_and_returns_retry_debug(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.tools._ANALYZE_RETRY_ATTEMPTS", 2)
    monkeypatch.setattr("app.agents.tools._ANALYZE_RETRY_DELAY_SECONDS", 0.0)

    attempts = {"count": 0}

    class FlakyGridicsClient:
        def __init__(self) -> None:
            self.call_log: list[dict[str, object]] = []

        def get_property_record(self, *, state_env: str, address: str, zip_code: str):
            attempts["count"] += 1
            self.call_log.append(
                {
                    "request": {
                        "path": "/property-record",
                        "params": {"state_env": state_env, "address": address, "zipCode": zip_code},
                    }
                }
            )
            if attempts["count"] == 1:
                raise RuntimeError("Gridics connection error: temporary outage")
            return {"mock": "payload"}

    def fake_build_gridics_client():
        return FlakyGridicsClient()

    def fake_extract_gridics_zoning_summary(payload):
        assert payload == {"mock": "payload"}
        return {
            "zone_combination_name": "R-3 Mixed",
            "typology": "Residential",
            "calculation_status": "ok",
            "notes": [],
            "constraints": {
                "max_far": 1.5,
                "max_units": 12,
                "max_height_ft": 45,
                "front_setback_ft": 10,
                "side_setback_ft": 5,
                "rear_setback_ft": 20,
            },
        }

    def fake_query_customer_zoning_code(*, query: str, limit: int, client_id: str, run_context=None):
        return {"query": query, "results": [{"name": "R-3 standards", "content": "Applies to R-3."}]}

    monkeypatch.setattr("app.agents.tools._build_gridics_client", fake_build_gridics_client)
    monkeypatch.setattr("app.agents.tools._extract_gridics_zoning_summary", fake_extract_gridics_zoning_summary)
    monkeypatch.setattr("app.agents.tools.query_customer_zoning_code", fake_query_customer_zoning_code)

    result = analyze_customer_zoning_request(
        query="Can I build an ADU at 123 Main Street, Springfield, IL 62704?",
        knowledge_limit=4,
        run_context=DummyRunContext({"client_id": "springfield"}),
    )

    assert attempts["count"] == 2
    assert result["retry_debug"]["recovered"] is True
    assert result["retry_debug"]["attempts"] == 2
    assert result["retry_debug"]["failed_attempts"][0]["attempt"] == 1
    assert result["retry_debug"]["failed_attempts"][0]["error_message"] == "Gridics connection error: temporary outage"
    assert result["retry_debug"]["failed_attempts"][0]["address_context"] == {
        "address_source": "query",
        "detected_address": "123 Main Street, Springfield, IL 62704",
        "standardized_address": "123 Main Street, Springfield, IL 62704",
        "state_env": "il",
        "zip_code": "62704",
    }
    assert result["retry_debug"]["failed_attempts"][0]["gridics_call_log"] == [
        {
            "request": {
                "path": "/property-record",
                "params": {
                    "state_env": "il",
                    "address": "123 Main Street",
                    "zipCode": "62704",
                },
            }
        }
    ]


def test_analyze_customer_zoning_request_surfaces_failure_diagnostics_after_retries(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.tools._ANALYZE_RETRY_ATTEMPTS", 2)
    monkeypatch.setattr("app.agents.tools._ANALYZE_RETRY_DELAY_SECONDS", 0.0)

    class BrokenGridicsClient:
        def __init__(self) -> None:
            self.call_log: list[dict[str, object]] = []

        def get_property_record(self, *, state_env: str, address: str, zip_code: str):
            self.call_log.append(
                {
                    "request": {
                        "path": "/property-record",
                        "params": {"state_env": state_env, "address": address, "zipCode": zip_code},
                    },
                    "error": "simulated upstream failure",
                }
            )
            raise RuntimeError("Gridics HTTP 502: bad gateway")

    monkeypatch.setattr("app.agents.tools._build_gridics_client", BrokenGridicsClient)

    try:
        analyze_customer_zoning_request(
            query="What can I build at 123 Main Street, Springfield, IL 62704?",
            run_context=DummyRunContext({"client_id": "springfield"}),
        )
    except RuntimeError as exc:
        diagnostics = json.loads(str(exc))
    else:  # pragma: no cover - explicit failure branch
        raise AssertionError("Expected analyze_customer_zoning_request to fail")

    assert diagnostics["message"] == "analyze_customer_zoning_request failed after 2 attempt(s)"
    assert len(diagnostics["failures"]) == 2
    assert diagnostics["failures"][0]["stage"] == "analyzing_request"
    assert diagnostics["failures"][0]["error_type"] == "RuntimeError"
    assert diagnostics["failures"][0]["error_message"] == "Gridics HTTP 502: bad gateway"
    assert diagnostics["failures"][0]["question_type"] == "specific_address"
    assert diagnostics["failures"][0]["gridics_call_log"] == [
        {
            "request": {
                "path": "/property-record",
                "params": {
                    "state_env": "il",
                    "address": "123 Main Street",
                    "zipCode": "62704",
                },
            },
            "error": "simulated upstream failure",
        }
    ]


def test_analyze_customer_zoning_request_blocks_non_zoning_scope(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("Knowledge retrieval should not run for blocked non-zoning prompts")

    monkeypatch.setattr("app.agents.tools.query_customer_zoning_code", fail_if_called)

    result = analyze_customer_zoning_request(
        query="What is the weather in Miami tomorrow?",
        run_context=DummyRunContext({"client_id": "springfield"}),
    )

    assert result["policy_decision"]["decision"] == "deny"
    assert result["policy_decision"]["reason_code"] == "non_zoning_scope"
    assert result["assistant_turn"]["intent_type"] == "out_of_scope"
    assert "zoning" in result["response_guardrail"]["message"].lower()


def test_analyze_customer_zoning_request_requests_scope_clarification(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("Knowledge retrieval should not run for scope clarification prompts")

    monkeypatch.setattr("app.agents.tools.query_customer_zoning_code", fail_if_called)

    result = analyze_customer_zoning_request(
        query="What can I do there?",
        run_context=DummyRunContext({"client_id": "springfield"}),
    )

    assert result["policy_decision"]["decision"] == "clarify"
    assert result["policy_decision"]["reason_code"] == "scope_ambiguous"
    assert result["assistant_turn"]["clarification_type"] == "scope"
    assert "clarify" in result["response_guardrail"]["message"].lower()


def test_analyze_customer_zoning_request_uses_tenant_default_zip_for_lookup(monkeypatch) -> None:
    gridics_calls: list[dict[str, str]] = []

    class FakeGridicsClient:
        call_log: list[dict[str, object]] = []

        def get_property_record(self, *, state_env: str, address: str, zip_code: str):
            gridics_calls.append({"state_env": state_env, "address": address, "zip_code": zip_code})
            return {"mock": "payload"}

    monkeypatch.setattr("app.agents.tools._build_gridics_client", lambda: FakeGridicsClient())
    monkeypatch.setattr(
        "app.agents.tools._extract_gridics_zoning_summary",
        lambda payload: {
            "resolved_city": "Springfield",
            "resolved_state": "IL",
            "zone_combination_name": "R-2",
            "typology": "Residential",
            "calculation_status": "ok",
            "notes": [],
            "constraints": {
                "max_far": 1.0,
                "max_units": 2,
                "max_height_ft": 35,
                "front_setback_ft": 10,
                "side_setback_ft": 5,
                "rear_setback_ft": 20,
            },
        },
    )
    monkeypatch.setattr("app.agents.tools.query_customer_zoning_code", lambda **kwargs: {"results": []})
    monkeypatch.setattr(
        "app.agents.tools._load_tenant_client",
        lambda client_id: DummyTenantClient(settings_json={"state": "il", "default_zip_code": "62704"}),
    )

    result = analyze_customer_zoning_request(
        query="What can I build at 123 Main Street, Springfield, IL?",
        run_context=DummyRunContext({"client_id": "springfield"}),
    )

    assert result["address_context"]["zip_code"] == "62704"
    assert result["address_context"]["address_source"] == "tenant_default_zip"
    assert gridics_calls == [
        {
            "state_env": "il",
            "address": "123 Main Street, Springfield, IL",
            "zip_code": "62704",
        }
    ]


def test_analyze_customer_zoning_request_allows_zipless_lookup_when_city_and_state_are_present(monkeypatch) -> None:
    gridics_calls: list[dict[str, object]] = []

    class FakeGridicsClient:
        call_log: list[dict[str, object]] = []

        def get_property_record(self, *, state_env: str, address: str, zip_code: str | None):
            gridics_calls.append({"state_env": state_env, "address": address, "zip_code": zip_code})
            return {"mock": "payload"}

    monkeypatch.setattr("app.agents.tools._build_gridics_client", lambda: FakeGridicsClient())
    monkeypatch.setattr(
        "app.agents.tools._extract_gridics_zoning_summary",
        lambda payload: {
            "resolved_city": "Miami",
            "resolved_state": "FL",
            "zone_combination_name": "T5-U",
            "typology": "Urban Center",
            "calculation_status": "ok",
            "notes": [],
            "constraints": {
                "max_far": 2.5,
                "max_units": 8,
                "max_height_ft": 55,
                "front_setback_ft": 10,
                "side_setback_ft": 5,
                "rear_setback_ft": 20,
            },
        },
    )
    monkeypatch.setattr("app.agents.tools.query_customer_zoning_code", lambda **kwargs: {"results": []})

    result = analyze_customer_zoning_request(
        query="How high can I build a fence on 3148 Mary St, Miami, FL?",
        run_context=DummyRunContext({"client_id": "springfield"}),
    )

    assert result["question_type"] == "specific_address"
    assert result["address_context"]["state_env"] == "fl"
    assert result["address_context"]["zip_code"] is None
    assert gridics_calls == [
        {
            "state_env": "fl",
            "address": "3148 Mary St",
            "zip_code": None,
        }
    ]


def test_analyze_customer_zoning_request_respects_jurisdiction_lock(monkeypatch) -> None:
    class FakeGridicsClient:
        call_log: list[dict[str, object]] = []

        def get_property_record(self, *, state_env: str, address: str, zip_code: str):
            return {"mock": "payload"}

    monkeypatch.setattr("app.agents.tools._build_gridics_client", lambda: FakeGridicsClient())
    monkeypatch.setattr(
        "app.agents.tools._extract_gridics_zoning_summary",
        lambda payload: {
            "resolved_city": "Springfield",
            "resolved_state": "IL",
            "zone_combination_name": "R-2",
            "typology": "Residential",
            "calculation_status": "ok",
            "notes": [],
            "constraints": {
                "max_far": 1.0,
                "max_units": 2,
                "max_height_ft": 35,
                "front_setback_ft": 10,
                "side_setback_ft": 5,
                "rear_setback_ft": 20,
            },
        },
    )
    monkeypatch.setattr("app.agents.tools.query_customer_zoning_code", lambda **kwargs: {"results": []})
    monkeypatch.setattr(
        "app.agents.tools._load_tenant_client",
        lambda client_id: DummyTenantClient(city_name="Miami", settings_json={"state": "fl", "default_zip_code": "33131"}),
    )
    run_context = DummyRunContext({"client_id": "springfield"})
    run_context.session_state["jurisdiction_lock"] = {"label": "Miami", "state": "fl"}
    result = analyze_customer_zoning_request(
        query="What can I build at 123 Main Street, Springfield, IL 62704?",
        run_context=run_context,
    )

    assert result["jurisdiction_resolution"]["jurisdiction_status"] == "out_of_jurisdiction"
    assert "locked to Miami" in result["response_guardrail"]["message"]
    assert result["confidence_band"] == "needs_verification"
