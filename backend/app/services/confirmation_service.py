"""Pending confirmation classification for property-address follow-ups."""

from __future__ import annotations

import json
import re
from typing import Any

from app.db.models import TenantClient
from app.db.session import SessionLocal
from app.services.platform_settings_service import get_platform_assistant_settings_json
from app.services.tenant_service import get_tenant_assistant_settings, merge_assistant_provider_keys

_PENDING_CONFIRMATION_AGENT_CACHE: dict[str, Any] = {}
_AFFIRMATION_PHRASES = {
    "yes",
    "yeah",
    "yep",
    "yup",
    "confirm",
    "confirmed",
    "continue",
    "proceed",
    "go ahead",
    "sounds good",
    "that's right",
    "that is right",
    "use that",
    "use it",
    "correct",
    "ok",
    "okay",
}
_ADDRESS_PATTERN = re.compile(
    r"\b\d{1,6}\s+[A-Za-z0-9][A-Za-z0-9.\-']*(?:\s+[A-Za-z0-9.\-']+){0,10}\b",
    flags=re.IGNORECASE,
)
_STREET_SUFFIX_PATTERN = re.compile(
    r"\b("
    r"street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|court|ct|way|"
    r"place|pl|terrace|ter|circle|cir|parkway|pkwy|highway|hwy"
    r")\.?\b",
    flags=re.IGNORECASE,
)


def _extract_text_from_agent_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    for attr in ("content", "output", "response", "text", "message"):
        value = getattr(result, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    return str(result)


def _invoke_agent_once(agent: Any, prompt: str) -> str | None:
    for method_name in ("run", "respond", "chat", "invoke"):
        method = getattr(agent, method_name, None)
        if callable(method):
            try:
                return _extract_text_from_agent_result(method(prompt))
            except Exception:
                return None
    return None


def _normalize(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _extract_address_candidate(query: str) -> str | None:
    match = _ADDRESS_PATTERN.search(query)
    if not match:
        return None
    candidate = query[match.start() :].strip(" ,.;:")
    return candidate if _STREET_SUFFIX_PATTERN.search(candidate) else None


def _resolve_confirmation_guardrail_api_key(tenant_client: TenantClient | None) -> tuple[str | None, str]:
    with SessionLocal() as db:
        platform_provider_keys, _ = get_tenant_assistant_settings(get_platform_assistant_settings_json(db))
    tenant_provider_keys, _ = get_tenant_assistant_settings(getattr(tenant_client, "settings_json", None))
    merged_provider_keys = merge_assistant_provider_keys(platform_provider_keys, tenant_provider_keys)
    gemini_key = merged_provider_keys.get("gemini")
    if gemini_key:
        return gemini_key, "tenant_db" if tenant_provider_keys.get("gemini") else "platform_db"
    return None, "missing"


def _build_pending_confirmation_agent(tenant_client: TenantClient | None = None):
    try:
        from app.agents.factory import build_agent_model, create_agent

        api_key, api_key_source = _resolve_confirmation_guardrail_api_key(tenant_client)
        if not api_key:
            return False
        cache_key = f"{api_key_source}:{api_key}"
        cached_agent = _PENDING_CONFIRMATION_AGENT_CACHE.get(cache_key)
        if cached_agent is not None:
            return cached_agent

        agent = create_agent(
            id="pending-property-confirmation-agent",
            name="Pending Property Confirmation Agent",
            model=build_agent_model(
                provider="gemini",
                model_id="gemini-2.5-flash-lite",
                api_key=api_key,
                allow_env_fallback=False,
            ),
            instructions=[
                "Classify whether a user reply should confirm a pending parcel address.",
                "Return only JSON with keys: decision, reason, confidence.",
                "decision must be one of: confirm_pending, clarify.",
                "confidence must be a float between 0 and 1.",
                "If the reply is clearly affirming the pending parcel, choose confirm_pending.",
                "If the reply is ambiguous or asks for clarification, choose clarify.",
            ],
        )
        setattr(agent, "_uzone_pending_confirmation_api_key_source", api_key_source)
        _PENDING_CONFIRMATION_AGENT_CACHE[cache_key] = agent
        return agent
    except Exception:
        return False


def _classify_pending_confirmation_with_agent(
    *,
    query: str,
    pending_context: dict[str, Any],
    tenant_client: TenantClient | None = None,
) -> dict[str, Any] | None:
    agent = _build_pending_confirmation_agent(tenant_client)
    if not agent:
        return None

    prompt = (
        "Classify this reply to a pending property-address confirmation.\n"
        f"Pending requested address: {pending_context.get('requested_address')}\n"
        f"Pending resolved address: {pending_context.get('resolved_address')}\n"
        f"User reply: {query}\n"
        "Return only JSON."
    )
    text = _invoke_agent_once(agent, prompt)
    if not text:
        return None

    try:
        parsed = json.loads(text)
    except Exception:
        return None

    decision = str(parsed.get("decision") or "").strip().lower()
    reason = str(parsed.get("reason") or "").strip() or "No reason provided by guardrail model."
    confidence_raw = parsed.get("confidence")
    try:
        confidence = float(confidence_raw)
    except Exception:
        confidence = 0.5

    if decision not in {"confirm_pending", "clarify"}:
        return None
    return {
        "decision": decision,
        "reason": reason,
        "confidence": max(0.0, min(1.0, confidence)),
    }


def build_pending_confirmation_prompt(*, pending_context: dict[str, Any], reason: str | None = None) -> str:
    resolved_address = str(pending_context.get("resolved_address") or "").strip() or "the resolved parcel"
    requested_address = str(pending_context.get("requested_address") or "").strip()
    parts = [
        f"I found a different parcel than the one you asked about: {resolved_address}.",
        "Please confirm that address or send the corrected address you want me to use.",
    ]
    if requested_address:
        parts[0] = f"The address you entered ({requested_address}) appears to resolve to {resolved_address}."
    if reason:
        parts.append(reason)
    return " ".join(parts)


def classify_pending_property_confirmation_response(
    *,
    query: str,
    pending_context: dict[str, Any] | None,
    tenant_client: TenantClient | None = None,
) -> dict[str, Any]:
    if not pending_context:
        return {
            "decision": "clarify",
            "reason": "No pending property confirmation is active.",
            "confidence": 0.0,
        }

    normalized = _normalize(query)
    candidate_address = _extract_address_candidate(query)
    if candidate_address:
        return {
            "decision": "clarify",
            "reason": "The reply includes a new address, so the caller should treat it as a new property lookup.",
            "confidence": 0.95,
        }

    agent_decision = _classify_pending_confirmation_with_agent(
        query=query,
        pending_context=pending_context,
        tenant_client=tenant_client,
    )
    if agent_decision is not None:
        if agent_decision["decision"] == "confirm_pending":
            return agent_decision
        return {
            **agent_decision,
            "clarification_prompt": build_pending_confirmation_prompt(
                pending_context=pending_context,
                reason=agent_decision["reason"],
            ),
        }

    if normalized in _AFFIRMATION_PHRASES:
        return {
            "decision": "confirm_pending",
            "reason": "The user gave a direct affirmative response to the pending confirmation.",
            "confidence": 0.98,
        }

    return {
        "decision": "clarify",
        "reason": "The reply was not a clear confirmation of the pending parcel.",
        "confidence": 0.5,
        "clarification_prompt": build_pending_confirmation_prompt(pending_context=pending_context),
    }
