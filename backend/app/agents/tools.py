"""Primary zoning tool module used by the Agno assistant stack.

This module keeps a stable public surface for the backend and test suite while
delegating the heavy zoning-request analysis flow to the dedicated runtime
implementation in `zoning_request_tools`.
"""

from __future__ import annotations

import json
from typing import Any

from app.agents import zoning_request_tools as _runtime
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


_ANALYZE_RETRY_ATTEMPTS = _runtime._ANALYZE_RETRY_ATTEMPTS
_ANALYZE_RETRY_DELAY_SECONDS = _runtime._ANALYZE_RETRY_DELAY_SECONDS
_build_gridics_client = _runtime._build_gridics_client
_extract_gridics_zoning_summary = _runtime._extract_gridics_zoning_summary
_extract_gridics_street_address = _runtime._extract_gridics_street_address
_load_tenant_client = _runtime._load_tenant_client
_standardize_address = _runtime._standardize_address
_runtime_query_customer_zoning_code = _runtime.query_customer_zoning_code
_RECENT_STANDARDIZED_ADDRESS_SESSION_KEY = "recent_standardized_address"


def _parse_failure_diagnostics(error: Exception) -> dict[str, Any] | None:
    try:
        payload = json.loads(str(error))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _build_graceful_failure_payload(
    *,
    operation: str,
    error: Exception,
    query: str | None = None,
    client_id: str | None = None,
    address: str | None = None,
    run_context: Any = None,
) -> dict[str, Any]:
    diagnostics = _parse_failure_diagnostics(error)
    query_text = str(query or "").strip()
    latest_failure = None
    if isinstance(diagnostics, dict):
        failures = diagnostics.get("failures")
        if isinstance(failures, list) and failures:
            latest_failure = failures[-1] if isinstance(failures[-1], dict) else None
    fallback_question_type = (
        str(latest_failure.get("question_type")).strip()
        if latest_failure and isinstance(latest_failure.get("question_type"), str) and str(latest_failure.get("question_type")).strip()
        else ("specific_address" if address else "general_zoning")
    )

    retry_debug = diagnostics if isinstance(diagnostics, dict) else {
        "message": str(error),
    }
    retry_debug["recovered"] = False
    retry_debug.setdefault("operation", operation)

    return {
        "question_type": fallback_question_type,
        "query": query_text or None,
        "client_id": client_id,
        "address_context": latest_failure.get("address_context") if latest_failure else None,
        "address_resolution": latest_failure.get("address_context") if latest_failure else None,
        "assistant_turn": {
            "intent_type": fallback_question_type,
            "policy_decision": {
                "decision": "clarify",
                "reason_code": "assistant_unavailable",
                "reason": "The zoning assistant could not complete the lookup right now.",
            },
            "jurisdiction_status": "needs_verification",
            "needs_clarification": True,
            "clarification_type": "service_error",
            "confidence": 0.1,
        },
        "request_classification": {
            "type": fallback_question_type,
            "label": "specific address" if fallback_question_type == "specific_address" else "general zoning",
            "reason": "The assistant could not complete the lookup right now.",
        },
        "response_guardrail": {
            "message": (
                "I couldn't complete the zoning lookup right now. Please try again in a moment or contact staff "
                "if the problem continues."
            ),
            "operation": operation,
            "error_type": type(error).__name__,
            "error_message": str(error),
        },
        "follow_up_context": {
            "context_type": fallback_question_type,
            "active_location": latest_failure.get("address_context") if latest_failure else None,
            "reuse_for_follow_ups": False,
            "guidance": "Try the same question again once the service is available.",
        },
        "retry_debug": retry_debug,
        "error": str(error),
    }


def _get_session_state(run_context: Any = None, **kwargs: Any) -> dict[str, Any] | None:
    session_state = kwargs.get("session_state")
    if isinstance(session_state, dict):
        return session_state
    run_context = kwargs.get("run_context", run_context)
    session_state = getattr(run_context, "session_state", None)
    return session_state if isinstance(session_state, dict) else None


def _get_context_property(run_context: Any = None, **kwargs: Any) -> dict[str, Any] | None:
    for source in (getattr(run_context, "dependencies", None), getattr(run_context, "metadata", None), kwargs.get("dependencies"), kwargs.get("metadata")):
        if not isinstance(source, dict):
            continue
        property_context = source.get("property")
        if isinstance(property_context, dict):
            return property_context
    return None


def _coerce_context_float(value: Any) -> float | None:
    if isinstance(value, (float, int)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _coordinates_from_property(property_context: dict[str, Any] | None) -> tuple[float | None, float | None]:
    if not property_context:
        return None, None
    latitude = _coerce_context_float(property_context.get("latitude"))
    longitude = _coerce_context_float(property_context.get("longitude"))
    center = property_context.get("center")
    if (latitude is None or longitude is None) and isinstance(center, list) and len(center) >= 2:
        longitude = _coerce_context_float(center[0])
        latitude = _coerce_context_float(center[1])
    return latitude, longitude


def _address_from_property(property_context: dict[str, Any] | None) -> str | None:
    if not property_context:
        return None
    for key in ("place_name", "address", "text"):
        value = property_context.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


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


def _sync_runtime_helpers() -> None:
    _runtime.query_customer_zoning_code = query_customer_zoning_code
    _runtime._build_gridics_client = _build_gridics_client
    _runtime._extract_gridics_zoning_summary = _extract_gridics_zoning_summary
    _runtime._extract_gridics_street_address = _extract_gridics_street_address
    _runtime._load_tenant_client = _load_tenant_client
    _runtime._ANALYZE_RETRY_ATTEMPTS = _ANALYZE_RETRY_ATTEMPTS
    _runtime._ANALYZE_RETRY_DELAY_SECONDS = _ANALYZE_RETRY_DELAY_SECONDS
    _runtime.classify_pending_property_confirmation_response = classify_pending_property_confirmation_response
    _runtime.build_pending_confirmation_prompt = build_pending_confirmation_prompt
    _runtime.build_evidence_pack = build_evidence_pack
    _runtime.citation_completeness_report = citation_completeness_report
    _runtime.grounding_verdict = grounding_verdict
    _runtime.evaluate_policy_decision = evaluate_policy_decision
    _runtime.resolve_jurisdiction_for_property_request = resolve_jurisdiction_for_property_request
    _runtime.insufficient_evidence_message = insufficient_evidence_message
    _runtime.jurisdiction_lock_message = jurisdiction_lock_message
    _runtime.missing_address_details_message = missing_address_details_message

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
    from app.agents.zoning_request_tools import _clear_pending_property_confirmation, _get_pending_property_confirmation
    from app.services.confirmation_service import (
        build_pending_confirmation_prompt,
        classify_pending_property_confirmation_response,
    )

    pending_context = _get_pending_property_confirmation(run_context or kwargs.get("run_context"))
    if not pending_context:
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
        return {
            "confirmed": True,
            "decision": response,
            "pending_context": pending_context,
        }

    if response.get("decision") == "clarify":
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
    try:
        return _runtime_query_customer_zoning_code(
            query=query,
            limit=limit,
            client_id=client_id,
            run_context=run_context or kwargs.get("run_context"),
        )
    except Exception as exc:
        return _build_graceful_failure_payload(
            operation="query_customer_zoning_code",
            error=exc,
            query=query,
            client_id=client_id,
            run_context=run_context or kwargs.get("run_context"),
        )


def analyze_customer_zoning_request(
    query: str | None = None,
    address: str | None = None,
    state_code: str | None = None,
    zip_code: str | int | None = None,
    latitude: float | int | str | None = None,
    longitude: float | int | str | None = None,
    knowledge_limit: int = 5,
    client_id: str | None = None,
    run_context: Any = None,
    **kwargs: Any,
) -> dict:
    _sync_runtime_helpers()
    effective_run_context = run_context or kwargs.get("run_context")
    property_context = _get_context_property(effective_run_context, **kwargs)
    context_latitude, context_longitude = _coordinates_from_property(property_context)
    if latitude is None:
        latitude = context_latitude
    if longitude is None:
        longitude = context_longitude
    if not address and latitude is not None and longitude is not None:
        address = _address_from_property(property_context)

    try:
        result = _runtime.analyze_customer_zoning_request(
            query=query,
            address=address,
            state_code=state_code,
            zip_code=zip_code,
            latitude=latitude,
            longitude=longitude,
            knowledge_limit=knowledge_limit,
            client_id=client_id,
            run_context=effective_run_context,
        )
    except Exception as exc:
        return _build_graceful_failure_payload(
            operation="analyze_customer_zoning_request",
            error=exc,
            query=query,
            client_id=client_id,
            address=address,
            run_context=effective_run_context,
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
