"""Compatibility layer for Agno zoning tools.

The backend tests still monkeypatch a handful of private helper names directly
off `app.agents.tools`, so this module keeps those names available while
delegating the heavy lifting to the richer legacy implementation in
`tools_backup`.
"""

from __future__ import annotations

from typing import Any

from app.agents import tools_backup as _legacy
from app.services.assistant_observability import append_policy_trace
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


def standardize_address(address: str, **kwargs: Any) -> str:
    return _standardize_address(address)


def confirm_pending_address(*, query: str | None = None, run_context: Any = None, **kwargs: Any) -> dict[str, Any]:
    from app.agents.tools_backup import _clear_pending_property_confirmation, _get_pending_property_confirmation
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
) -> dict:
    return _legacy_query_customer_zoning_code(
        query=query,
        limit=limit,
        client_id=client_id,
        run_context=run_context,
    )


def analyze_customer_zoning_request(
    query: str,
    address: str | None = None,
    state_env: str | None = None,
    zip_code: str | int | None = None,
    knowledge_limit: int = 5,
    client_id: str | None = None,
    run_context: Any = None,
) -> dict:
    _sync_legacy_helpers()
    return _legacy.analyze_customer_zoning_request(
        query=query,
        address=address,
        state_env=state_env,
        zip_code=zip_code,
        knowledge_limit=knowledge_limit,
        client_id=client_id,
        run_context=run_context,
    )


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
