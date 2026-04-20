"""Compatibility layer for Agno zoning tools.

The backend tests still monkeypatch a handful of private helper names directly
off `app.agents.tools`, so this module keeps those names available while
delegating the heavy lifting to the richer legacy implementation in
`legacy_tools`.
"""

from __future__ import annotations

from typing import Any

from app.agents import legacy_tools as _legacy
from app.services.assistant_observability import append_policy_trace
from app.services.assistant_observability import append_run_trace
from app.services.confirmation_service import (
    build_pending_confirmation_prompt,
    classify_pending_property_confirmation_response,
)
from app.services.jurisdiction_resolver import resolve_jurisdiction_for_property_request
from app.services.policy_service import evaluate_policy_decision
from app.services.response_grounding import build_evidence_pack, citation_completeness_report, grounding_verdict
from app.services.response_templates import (
    insufficient_evidence_message,
    jurisdiction_lock_message,
    missing_address_details_message,
)


_ANALYZE_RETRY_ATTEMPTS = _legacy._ANALYZE_RETRY_ATTEMPTS
_ANALYZE_RETRY_DELAY_SECONDS = _legacy._ANALYZE_RETRY_DELAY_SECONDS
_build_gridics_client = _legacy._build_gridics_client
_extract_gridics_zoning_summary = _legacy._extract_gridics_zoning_summary
_extract_gridics_street_address = _legacy._extract_gridics_street_address
_load_tenant_client = _legacy._load_tenant_client
_standardize_address = _legacy._standardize_address
_legacy_query_customer_zoning_code = _legacy.query_customer_zoning_code
_RECENT_STANDARDIZED_ADDRESS_SESSION_KEY = "recent_standardized_address"


def _get_session_state(run_context: Any = None, **kwargs: Any) -> dict[str, Any] | None:
    session_state = kwargs.get("session_state")
    if isinstance(session_state, dict):
        return session_state
    session_state = getattr(run_context, "session_state", None)
    return session_state if isinstance(session_state, dict) else None


def _normalize_address_text(address: str | None) -> str:
    if not isinstance(address, str):
        return ""
    return "".join(ch.lower() for ch in address if ch.isalnum())


def _get_recent_standardized_address(run_context: Any = None, **kwargs: Any) -> str | None:
    session_state = _get_session_state(run_context, **kwargs)
    if not session_state:
        return None
    recent = session_state.get(_RECENT_STANDARDIZED_ADDRESS_SESSION_KEY)
    if not isinstance(recent, dict):
        return None
    standardized_address = str(recent.get("standardized_address") or "").strip()
    return standardized_address or None


def _store_recent_standardized_address(run_context: Any = None, payload: dict[str, Any] | None = None, **kwargs: Any) -> None:
    session_state = _get_session_state(run_context, **kwargs)
    if session_state is None:
        return
    payload = payload or {}
    session_state[_RECENT_STANDARDIZED_ADDRESS_SESSION_KEY] = {
        "input_address": str(payload.get("input_address") or "").strip(),
        "standardized_address": str(payload.get("standardized_address") or "").strip(),
        "needs_confirmation": bool(payload.get("needs_confirmation")),
        "same_as_input": bool(payload.get("same_as_input")),
    }

def _prefer_recent_standardized_address(address: str | None, run_context: Any = None, **kwargs: Any) -> str | None:
    normalized_address = str(address or "").strip()
    if not normalized_address:
        return _get_recent_standardized_address(run_context, **kwargs)

    recent_standardized_address = _get_recent_standardized_address(run_context, **kwargs)
    if not recent_standardized_address:
        return normalized_address

    normalized_recent = _normalize_address_text(recent_standardized_address)
    normalized_current = _normalize_address_text(normalized_address)

    if normalized_current == normalized_recent:
        return recent_standardized_address

    if normalized_current and normalized_recent.startswith(normalized_current):
        return recent_standardized_address

    return normalized_address


def _append_tool_trace(run_context: Any, event: dict[str, Any]) -> None:
    append_run_trace(run_context, {"category": "tool", **event})


def _sync_legacy_helpers() -> None:
    _legacy.query_customer_zoning_code = query_customer_zoning_code
    _legacy._build_gridics_client = _build_gridics_client
    _legacy._extract_gridics_zoning_summary = _extract_gridics_zoning_summary
    _legacy._extract_gridics_street_address = _extract_gridics_street_address
    _legacy._load_tenant_client = _load_tenant_client
    _legacy._ANALYZE_RETRY_ATTEMPTS = _ANALYZE_RETRY_ATTEMPTS
    _legacy._ANALYZE_RETRY_DELAY_SECONDS = _ANALYZE_RETRY_DELAY_SECONDS
    _legacy.classify_pending_property_confirmation_response = classify_pending_property_confirmation_response
    _legacy.build_pending_confirmation_prompt = build_pending_confirmation_prompt
    _legacy.build_evidence_pack = build_evidence_pack
    _legacy.citation_completeness_report = citation_completeness_report
    _legacy.grounding_verdict = grounding_verdict
    _legacy.append_policy_trace = append_policy_trace
    _legacy.evaluate_policy_decision = evaluate_policy_decision
    _legacy.resolve_jurisdiction_for_property_request = resolve_jurisdiction_for_property_request
    _legacy.insufficient_evidence_message = insufficient_evidence_message
    _legacy.jurisdiction_lock_message = jurisdiction_lock_message
    _legacy.missing_address_details_message = missing_address_details_message

def standardize_address(address: str, **kwargs: Any) -> dict[str, Any]:
    normalized = str(address or "").strip()
    standardized = _standardize_address(normalized)
    result = {
        "input_address": normalized,
        "standardized_address": standardized,
        "needs_confirmation": bool(normalized and standardized != normalized),
        "same_as_input": standardized == normalized,
    }
    _store_recent_standardized_address(payload=result, **kwargs)
    return result


def confirm_pending_address(*, query: str | None = None, run_context: Any = None, **kwargs: Any) -> dict[str, Any]:
    from app.agents.legacy_tools import _clear_pending_property_confirmation, _get_pending_property_confirmation
    from app.services.confirmation_service import (
        build_pending_confirmation_prompt,
        classify_pending_property_confirmation_response,
    )

    pending_context = _get_pending_property_confirmation(run_context or kwargs.get("run_context"))
    if not pending_context:
        _append_tool_trace(
            run_context or kwargs.get("run_context"),
            {
                "event": "tool.confirm_pending_address",
                "status": "no_pending_context",
            },
        )
        return {
            "confirmed": False,
            "needs_confirmation": False,
            "message": "No pending address confirmation is active.",
        }

    response = classify_pending_property_confirmation_response(
        query=query or "",
        pending_context=pending_context,
        tenant_client=kwargs.get("tenant_client"),
    )
    if response.get("decision") == "confirm_pending":
        _clear_pending_property_confirmation(run_context or kwargs.get("run_context"))
        _append_tool_trace(
            run_context or kwargs.get("run_context"),
            {
                "event": "tool.confirm_pending_address",
                "status": "confirmed",
                "decision": response,
            },
        )
        return {
            "confirmed": True,
            "decision": response,
            "pending_context": pending_context,
        }

    if response.get("decision") == "clarify":
        _append_tool_trace(
            run_context or kwargs.get("run_context"),
            {
                "event": "tool.confirm_pending_address",
                "status": "clarify",
                "decision": response,
            },
        )
        return {
            "confirmed": False,
            "needs_confirmation": True,
            "message": response.get("clarification_prompt")
            or build_pending_confirmation_prompt(
                pending_context=pending_context,
                reason=str(response.get("reason") or "").strip() or None,
            ),
            "decision": response,
        }

    _append_tool_trace(
        run_context or kwargs.get("run_context"),
        {
            "event": "tool.confirm_pending_address",
            "status": "not_confirmed",
            "decision": response,
        },
    )
    return {
        "confirmed": False,
        "decision": response,
        "pending_context": pending_context,
    }


def query_customer_zoning_code(
    query: str,
    limit: int = 5,
    client_id: str | None = None,
    run_context: Any = None,
    **kwargs: Any,
) -> dict:
    _append_tool_trace(
        run_context,
        {
            "event": "tool.query_customer_zoning_code",
            "query": query,
            "limit": limit,
            "client_id": client_id,
        },
    )
    return _legacy_query_customer_zoning_code(
        query=query,
        limit=limit,
        client_id=client_id,
        run_context=run_context or kwargs.get("run_context"),
    )


def analyze_customer_zoning_request(
    query: str | None = None,
    address: str | None = None,
    state_env: str | None = None,
    zip_code: str | int | None = None,
    knowledge_limit: int = 5,
    client_id: str | None = None,
    run_context: Any = None,
    **kwargs: Any,
) -> dict:
    _append_tool_trace(
        run_context,
        {
            "event": "tool.analyze_customer_zoning_request",
            "query": query,
            "address": address,
            "state_env": state_env,
            "zip_code": zip_code,
            "knowledge_limit": knowledge_limit,
            "client_id": client_id,
        },
    )
    _sync_legacy_helpers()
    effective_query = str(query or "").strip()
    preferred_address = _prefer_recent_standardized_address(address, run_context, **kwargs)
    if not effective_query:
        effective_query = (
            f"What are the zoning rules for {preferred_address}?"
            if preferred_address
            else "What are the zoning rules for this property?"
        )
    return _legacy.analyze_customer_zoning_request(
        query=effective_query,
        address=preferred_address,
        state_env=state_env,
        zip_code=zip_code,
        knowledge_limit=knowledge_limit,
        client_id=client_id,
        run_context=run_context,
    )
    _append_tool_trace(
        run_context,
        {
            "event": "tool.analyze_customer_zoning_request.complete",
            "client_id": client_id,
            "result_keys": sorted(result.keys()) if isinstance(result, dict) else None,
        },
    )
    return result


__all__ = [
    "standardize_address",
    "confirm_pending_address",
    "query_customer_zoning_code",
    "analyze_customer_zoning_request",
    "_ANALYZE_RETRY_ATTEMPTS",
    "_ANALYZE_RETRY_DELAY_SECONDS",
    "_build_gridics_client",
    "_extract_gridics_zoning_summary",
    "_extract_gridics_street_address",
    "_load_tenant_client",
    "_standardize_address",
    "append_policy_trace",
    "build_evidence_pack",
    "build_pending_confirmation_prompt",
    "citation_completeness_report",
    "classify_pending_property_confirmation_response",
    "evaluate_policy_decision",
    "grounding_verdict",
    "insufficient_evidence_message",
    "jurisdiction_lock_message",
    "missing_address_details_message",
    "resolve_jurisdiction_for_property_request",
]
