"""Assistant policy guardrails for zoning scope and jurisdiction boundaries.

This module uses a hybrid approach:
1) Gemini-backed Agno guardrail classifier when available.
2) Deterministic fallback rules when model execution is unavailable.
"""

from __future__ import annotations

import re
import json
from typing import Any

from app.db.models import TenantClient
from app.db.session import SessionLocal
from app.services.agentic.jurisdiction_resolver import normalize_city_name
from app.services.shared.platform_settings_service import get_platform_assistant_settings_json
from app.services.shared.tenant_service import get_tenant_assistant_settings, merge_assistant_provider_keys

_ZONING_KEYWORDS = (
    "zoning",
    "zone",
    "setback",
    "height",
    "far",
    "floor area ratio",
    "parcel",
    "lot",
    "overlay",
    "land use",
    "permitted use",
    "adu",
    "duplex",
    "triplex",
    "density",
)

_NON_ZONING_STRONG_SIGNALS = (
    "mortgage",
    "interest rate",
    "recipe",
    "weather",
    "sports",
    "stock price",
    "bitcoin",
    "vacation",
)

_SCOPE_GUARDRAIL_AGENT_CACHE: dict[str, Any] = {}
_ALLOWED_SCOPE_LABELS = {"zoning", "non_zoning", "ambiguous"}


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


def _resolve_scope_guardrail_api_key(tenant_client: TenantClient | None) -> tuple[str | None, str]:
    with SessionLocal() as db:
        platform_provider_keys, _ = get_tenant_assistant_settings(get_platform_assistant_settings_json(db))
    tenant_provider_keys, _ = get_tenant_assistant_settings(getattr(tenant_client, "settings_json", None))
    merged_provider_keys = merge_assistant_provider_keys(platform_provider_keys, tenant_provider_keys)
    gemini_key = merged_provider_keys.get("gemini")
    if gemini_key:
        return gemini_key, "tenant_db" if tenant_provider_keys.get("gemini") else "platform_db"
    return None, "missing"


def _build_scope_guardrail_agent(tenant_client: TenantClient | None = None):
    try:
        from agno.agent import Agent
        from agno.models.google import Gemini

        api_key, api_key_source = _resolve_scope_guardrail_api_key(tenant_client)
        if not api_key:
            return False
        cache_key = f"{api_key_source}:{api_key}"
        cached_agent = _SCOPE_GUARDRAIL_AGENT_CACHE.get(cache_key)
        if cached_agent is not None:
            return cached_agent

        agent = Agent(
            id="scope-guardrail-agent",
            name="Scope Guardrail Agent",
            model=Gemini(id="gemini-2.5-flash-lite", api_key=api_key),
            instructions=[
                "Classify if a user prompt is zoning-related.",
                "Return only JSON with keys: label, reason, confidence.",
                "label must be one of: zoning, non_zoning, ambiguous.",
                "confidence must be a float between 0 and 1.",
            ],
        )
        setattr(agent, "_uzone_scope_guardrail_api_key_source", api_key_source)
        _SCOPE_GUARDRAIL_AGENT_CACHE[cache_key] = agent
        return agent
    except Exception:
        return False


def _classify_scope_with_agent(query: str, tenant_client: TenantClient | None = None) -> tuple[str, str] | None:
    agent = _build_scope_guardrail_agent(tenant_client)
    if not agent:
        return None

    prompt = (
        "Classify this prompt for municipal zoning assistant scope.\n"
        f"Prompt: {query}\n"
        "Return only JSON."
    )
    text = _invoke_agent_once(agent, prompt)
    if not text:
        return None

    try:
        parsed = json.loads(text)
    except Exception:
        return None

    label = str(parsed.get("label") or "").strip().lower()
    reason = str(parsed.get("reason") or "").strip() or "No reason provided by guardrail model."
    if label not in _ALLOWED_SCOPE_LABELS:
        return None
    if label == "zoning":
        return "allow", reason
    if label == "non_zoning":
        return "deny_non_zoning", reason
    return "clarify_scope", reason


def classify_scope(query: str, tenant_client: TenantClient | None = None) -> tuple[str, str]:
    """Classify whether a prompt is zoning-related."""
    normalized = query.strip().lower()
    if not normalized:
        return "clarify", "Please provide your zoning question."

    try:
        agent_decision = _classify_scope_with_agent(query, tenant_client=tenant_client)
    except TypeError:
        agent_decision = _classify_scope_with_agent(query)
    if agent_decision is not None:
        return agent_decision

    if any(signal in normalized for signal in _NON_ZONING_STRONG_SIGNALS) and not any(
        keyword in normalized for keyword in _ZONING_KEYWORDS
    ):
        return "deny_non_zoning", "This assistant only supports zoning and land-use questions."

    if any(keyword in normalized for keyword in _ZONING_KEYWORDS):
        return "allow", "Question appears to be zoning-related."

    # default to clarification instead of denial to avoid false negatives
    if re.search(r"\b(can|what|how|is|are)\b", normalized):
        return "clarify_scope", "Please clarify your zoning or land-use question."

    return "allow", "No explicit non-zoning signal detected."


def evaluate_policy_decision(
    *,
    query: str,
    question_type: str,
    tenant_client: TenantClient | None,
    resolved_city: str | None = None,
    resolved_state: str | None = None,
) -> dict[str, Any]:
    """Return an enforceable policy decision for assistant execution."""
    scope_decision, scope_reason = classify_scope(query, tenant_client=tenant_client)
    if scope_decision in {"deny_non_zoning"}:
        return {
            "decision": "deny",
            "reason_code": "non_zoning_scope",
            "reason": scope_reason,
        }

    if scope_decision == "clarify_scope" and question_type != "specific_address":
        return {
            "decision": "clarify",
            "reason_code": "scope_ambiguous",
            "reason": scope_reason,
        }

    if question_type != "specific_address":
        return {
            "decision": "allow",
            "reason_code": "general_zoning_in_scope",
            "reason": "General zoning question for tenant-scoped knowledge.",
        }

    if tenant_client and resolved_city:
        tenant_city = normalize_city_name(tenant_client.city_name)
        record_city = normalize_city_name(resolved_city)
        if tenant_city and record_city and tenant_city != record_city:
            return {
                "decision": "deny",
                "reason_code": "outside_jurisdiction_city_mismatch",
                "reason": (
                    f"This property appears to be in {resolved_city}, "
                    f"but this assistant is configured for {tenant_client.city_name}."
                ),
            }

    if tenant_client and resolved_state and tenant_client.settings_json:
        configured_state = str((tenant_client.settings_json or {}).get("state") or "").strip().lower()
        if configured_state and configured_state != resolved_state.strip().lower():
            return {
                "decision": "deny",
                "reason_code": "outside_jurisdiction_state_mismatch",
                "reason": "This property appears to be outside the tenant's configured state.",
            }

    return {
        "decision": "allow",
        "reason_code": "in_scope",
        "reason": "Request is within zoning scope and jurisdiction constraints.",
    }
