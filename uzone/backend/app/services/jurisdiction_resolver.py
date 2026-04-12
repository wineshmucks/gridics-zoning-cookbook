"""Jurisdiction resolution helpers for property-specific assistant requests."""

from __future__ import annotations

from typing import Any

from app.db.models import TenantClient


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def resolve_jurisdiction_for_property_request(
    *,
    tenant_client: TenantClient | None,
    standardized_address: str | None,
    lookup_ready: bool,
    resolved_city: str | None = None,
    resolved_state: str | None = None,
) -> dict[str, Any]:
    """Resolve whether a specific-property request is in the current tenant jurisdiction."""
    tenant_city = _normalize(getattr(tenant_client, "city_name", None))
    tenant_state = _normalize(
        str((getattr(tenant_client, "settings_json", {}) or {}).get("state") or "")
    )
    record_city = _normalize(resolved_city)
    record_state = _normalize(resolved_state)

    if not lookup_ready:
        suggestion_parts = [part for part in [standardized_address, tenant_client.city_name if tenant_client else None] if part]
        if tenant_state:
            suggestion_parts.append(tenant_state.upper())
        suggestion = ", ".join(suggestion_parts) if suggestion_parts else None
        candidates = [suggestion] if suggestion else []
        return {
            "jurisdiction_status": "unresolved",
            "is_ambiguous": True,
            "clarification_type": "address_missing_details",
            "clarification_prompt": "Please confirm the full property address, including state and ZIP code.",
            "clarification_candidates": candidates,
        }

    if tenant_city and record_city and tenant_city != record_city:
        return {
            "jurisdiction_status": "out_of_jurisdiction",
            "is_ambiguous": False,
            "clarification_type": "jurisdiction_mismatch",
            "clarification_prompt": (
                f"This address appears to be in {resolved_city}. "
                f"This assistant is currently scoped to {tenant_client.city_name}."
            ),
            "clarification_candidates": [],
        }

    if tenant_state and record_state and tenant_state != record_state:
        return {
            "jurisdiction_status": "out_of_jurisdiction",
            "is_ambiguous": False,
            "clarification_type": "jurisdiction_mismatch",
            "clarification_prompt": (
                f"This address appears to be in {resolved_state}. "
                f"This assistant is currently scoped to {tenant_state.upper()}."
            ),
            "clarification_candidates": [],
        }

    return {
        "jurisdiction_status": "in_jurisdiction",
        "is_ambiguous": False,
        "clarification_type": "none",
        "clarification_prompt": None,
        "clarification_candidates": [],
    }
