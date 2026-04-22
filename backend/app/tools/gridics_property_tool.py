"""Agno-friendly property context lookup tool."""

from __future__ import annotations

from typing import Any

from app.schemas.property_context import PropertyContextResult
from app.services.agentic.property_context_service import GridicsPropertyContextService


def _get_run_context_value(run_context: Any, key: str, **kwargs: Any) -> Any:
    dependencies = kwargs.get("dependencies")
    if not isinstance(dependencies, dict):
        dependencies = getattr(run_context, "dependencies", None)
    if isinstance(dependencies, dict) and dependencies.get(key) not in (None, ""):
        return dependencies.get(key)

    session_state = kwargs.get("session_state")
    if not isinstance(session_state, dict):
        session_state = getattr(run_context, "session_state", None)
    if isinstance(session_state, dict):
        active_property_context = session_state.get("active_property_context")
        if isinstance(active_property_context, dict) and active_property_context.get(key) not in (None, ""):
            return active_property_context.get(key)
        if session_state.get(key) not in (None, ""):
            return session_state.get(key)

    return None


def _normalize_state_env(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().split(",")[-1].strip().lower()
    if len(candidate) == 2 and candidate.isalpha():
        return candidate
    return None


def get_property_context(
    lat: float,
    lng: float,
    state_env: str = "",
    jurisdiction_id: str = "",
    jurisdiction_name: str | None = None,
    address: str | None = None,
    run_context: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Return normalized property context for the given map coordinates."""

    resolved_state_env = (state_env or "").strip() or _get_run_context_value(
        run_context,
        "state_env",
        dependencies=kwargs.get("dependencies"),
        session_state=kwargs.get("session_state"),
    )
    resolved_jurisdiction_id = (jurisdiction_id or "").strip() or _get_run_context_value(
        run_context,
        "jurisdiction_id",
        dependencies=kwargs.get("dependencies"),
        session_state=kwargs.get("session_state"),
    )
    resolved_jurisdiction_name = jurisdiction_name or _get_run_context_value(
        run_context,
        "jurisdiction_name",
        dependencies=kwargs.get("dependencies"),
        session_state=kwargs.get("session_state"),
    )
    resolved_address = address or _get_run_context_value(
        run_context,
        "address",
        dependencies=kwargs.get("dependencies"),
        session_state=kwargs.get("session_state"),
    )

    resolved_state_env = _normalize_state_env(resolved_state_env)
    if not resolved_state_env:
        return {
            "status": "error",
            "error_message": "Internal tenant context is missing a valid two-letter state_env. Call get_active_tenant_context or get_tenant_context and retry; do not ask the user for state_env.",
            "missing_fields": ["state_env"],
        }
    if not resolved_jurisdiction_id:
        return {
            "status": "error",
            "error_message": "Internal tenant context is missing jurisdiction_id. Call get_active_tenant_context or get_tenant_context and retry; do not ask the user for jurisdiction_id.",
            "missing_fields": ["jurisdiction_id"],
        }

    print(f"[get_property_context] Fetching property context for coordinates: ({lat}, {lng}) in jurisdiction {resolved_jurisdiction_name} (ID: {resolved_jurisdiction_id}) state_env={resolved_state_env}")
    print(f"[get_property_context] Address: {resolved_address}")
    service = GridicsPropertyContextService()
    result: PropertyContextResult = service.get_property_context(
        lat=lat,
        lng=lng,
        state_env=str(resolved_state_env),
        jurisdiction_id=str(resolved_jurisdiction_id),
        jurisdiction_name=str(resolved_jurisdiction_name) if resolved_jurisdiction_name else None,
        address=str(resolved_address) if resolved_address else None,
    )
    return result.model_dump(mode="json", exclude={"raw_response"})
