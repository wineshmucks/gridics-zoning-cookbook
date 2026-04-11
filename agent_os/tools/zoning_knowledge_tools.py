"""Agno tools for customer zoning knowledge retrieval."""

from __future__ import annotations

from pathlib import Path
import sys


def _ensure_backend_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    backend_root = repo_root / "uzone" / "backend"
    backend_root_str = str(backend_root)
    if backend_root_str not in sys.path:
        sys.path.insert(0, backend_root_str)


def query_customer_zoning_code(client_id: str, query: str, limit: int = 5) -> dict:
    """Query the ingested zoning code corpus for a customer by client_id."""
    _ensure_backend_on_path()

    from sqlalchemy import select

    from app.db.models import TenantClient
    from app.db.session import SessionLocal
    from app.services.zoning_knowledge_service import query_customer_zoning_knowledge

    with SessionLocal() as db:
        tenant_client = db.scalar(select(TenantClient).where(TenantClient.client_id == client_id))
        if tenant_client is None:
            raise ValueError(f"Unknown tenant client_id '{client_id}'")
        return query_customer_zoning_knowledge(db, tenant_client, query=query, limit=limit)
