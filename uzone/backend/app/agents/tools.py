"""Agno tools backed by UZone services."""

from __future__ import annotations

from typing import Any


def query_customer_zoning_code(
    query: str,
    limit: int = 5,
    client_id: str | None = None,
    run_context: Any = None,
) -> dict:
    """Query zoning knowledge for one specific tenant by client_id."""
    resolved_client_id = client_id
    dependencies = getattr(run_context, "dependencies", None)
    if not resolved_client_id and isinstance(dependencies, dict):
        dependency_client_id = dependencies.get("client_id")
        if isinstance(dependency_client_id, str) and dependency_client_id.strip():
            resolved_client_id = dependency_client_id.strip()

    if not resolved_client_id:
        raise ValueError("client_id is required to query customer zoning knowledge.")

    from sqlalchemy import select

    from app.db.models import TenantClient
    from app.db.session import SessionLocal
    from app.services.zoning_knowledge_service import query_customer_zoning_knowledge

    with SessionLocal() as db:
        tenant_client = db.scalar(select(TenantClient).where(TenantClient.client_id == resolved_client_id))
        if tenant_client is None:
            raise ValueError(f"Unknown tenant client_id '{resolved_client_id}'")
        return query_customer_zoning_knowledge(db, tenant_client, query=query, limit=limit)
