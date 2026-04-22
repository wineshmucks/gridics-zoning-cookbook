"""Agno-friendly tenant context lookup tool."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.agents.agent_utils import _get_client_id
from app.db.session import SessionLocal
from app.services.shared.tenant_service import resolve_tenant_public_config_by_identifier


class TenantContextSummary(BaseModel):
    client_id: str | None = None
    jurisdiction_id: str | None = None
    market_served: str | None = None
    state_env: str | None = None
    found: bool = False


def _parse_state_env(market_served: str | None) -> str | None:
    if not isinstance(market_served, str):
        return None
    parts = [part.strip() for part in market_served.split(",") if part.strip()]
    if len(parts) < 2:
        return None
    state_env = parts[-1].lower()
    return state_env or None


def _get_jurisdiction_id(run_context: Any = None, **kwargs: Any) -> str | None:
    dependencies = kwargs.get("dependencies")
    if not isinstance(dependencies, dict):
        dependencies = getattr(run_context, "dependencies", None)
    if not isinstance(dependencies, dict):
        return None
    jurisdiction_id = dependencies.get("jurisdiction_id")
    return jurisdiction_id.strip() if isinstance(jurisdiction_id, str) and jurisdiction_id.strip() else None


def get_tenant_context(
    client_id: str | None = None,
    jurisdiction_id: str | None = None,
    run_context: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Return the current tenant context for a client or jurisdiction identifier."""

    resolved_client_id = (
        _get_client_id(run_context, dependencies=kwargs.get("dependencies"))
        if client_id is None
        else client_id.strip() or None
    )
    resolved_jurisdiction_id = (
        _get_jurisdiction_id(run_context, dependencies=kwargs.get("dependencies"))
        if jurisdiction_id is None
        else jurisdiction_id.strip() or None
    )

    with SessionLocal() as db:
        config = resolve_tenant_public_config_by_identifier(
            db,
            client_id=resolved_client_id,
            jurisdiction_id=resolved_jurisdiction_id,
        )

    if config is None:
        summary = TenantContextSummary(
            client_id=resolved_client_id,
            jurisdiction_id=resolved_jurisdiction_id,
        )
    else:
        summary = TenantContextSummary(
            client_id=config.client_id,
            jurisdiction_id=config.jurisdiction_id,
            market_served=config.market_served,
            state_env=_parse_state_env(config.market_served),
            found=True,
        )

    print(
        "[get_tenant_context] "
        f"client_id={summary.client_id} "
        f"jurisdiction_id={summary.jurisdiction_id} "
        f"market_served={summary.market_served} "
        f"found={summary.found}"
    )
    return summary.model_dump()
