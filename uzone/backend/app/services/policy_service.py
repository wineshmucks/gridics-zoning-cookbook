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

_SCOPE_GUARDRAIL_AGENT = None
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


def _build_scope_guardrail_agent():
    global _SCOPE_GUARDRAIL_AGENT
    if _SCOPE_GUARDRAIL_AGENT is not None:
        return _SCOPE_GUARDRAIL_AGENT
    try:
        from app.agents.factory import build_agent_model, create_agent

        _SCOPE_GUARDRAIL_AGENT = create_agent(
            id="scope-guardrail-agent",
            name="Scope Guardrail Agent",
            model=build_agent_model(
                provider="gemini",
                model_id="gemini-flash-lite-latest",
                allow_env_fallback=True,
            ),
            instructions=[
                "Classify if a user prompt is zoning-related.",
                "Return only JSON with keys: label, reason, confidence.",
                "label must be one of: zoning, non_zoning, ambiguous.",
                "confidence must be a float between 0 and 1.",
            ],
        )
    except Exception:
        _SCOPE_GUARDRAIL_AGENT = False
    return _SCOPE_GUARDRAIL_AGENT


def _classify_scope_with_agent(query: str) -> tuple[str, str] | None:
    agent = _build_scope_guardrail_agent()
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


def classify_scope(query: str) -> tuple[str, str]:
    """Classify whether a prompt is zoning-related."""
    normalized = query.strip().lower()
    if not normalized:
        return "clarify", "Please provide your zoning question."

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
    scope_decision, scope_reason = classify_scope(query)
    if scope_decision in {"deny_non_zoning"}:
        return {
            "decision": "deny",
            "reason_code": "non_zoning_scope",
            "reason": scope_reason,
        }

    if scope_decision == "clarify_scope":
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
        tenant_city = (tenant_client.city_name or "").strip().lower()
        record_city = resolved_city.strip().lower()
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
