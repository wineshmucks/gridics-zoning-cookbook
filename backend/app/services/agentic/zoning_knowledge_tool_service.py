"""Typed zoning knowledge retrieval service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_, select

from app.db.models import TenantClient
from app.db.session import SessionLocal
from app.services.shared.citation_formatter import build_knowledge_citation
from app.services.agentic.zoning_knowledge_service import query_customer_zoning_knowledge


@dataclass(slots=True)
class ZoningKnowledgeLookupService:
    """Resolve a tenant and fetch authoritative zoning knowledge snippets."""

    def retrieve(self, *, jurisdiction_id: str, question: str, limit: int = 5) -> dict[str, Any]:
        with SessionLocal() as db:
            tenant_client = db.scalar(
                select(TenantClient).where(
                    or_(
                        TenantClient.client_id == jurisdiction_id,
                        TenantClient.jurisdiction_id == jurisdiction_id,
                    )
                )
            )
            if tenant_client is None:
                return {
                    "query": question,
                    "results": [],
                    "error": f"Unknown jurisdiction '{jurisdiction_id}'",
                }

            payload = query_customer_zoning_knowledge(
                db,
                tenant_client,
                query=question,
                limit=limit,
            )

        normalized_results: list[dict[str, Any]] = []
        for index, result in enumerate(payload.get("results") or [], start=1):
            metadata = result.get("meta_data") if isinstance(result, dict) else {}
            if not isinstance(metadata, dict):
                metadata = {}
            label = str(
                metadata.get("section_title")
                or result.get("name")
                or f"Zoning code result {index}"
            ).strip()
            citation = build_knowledge_citation(
                citation_id=f"code-{index}",
                label=label,
                section=str(metadata.get("section_key") or "").strip() or None,
                excerpt=str(result.get("content") or "").strip()[:500] or None,
                url=str(metadata.get("section_url") or metadata.get("source_url") or "").strip() or None,
                metadata={"source_url": metadata.get("source_url")},
            )
            normalized_results.append(
                {
                    "id": citation.id,
                    "label": citation.label,
                    "section": citation.section,
                    "excerpt": citation.excerpt,
                    "url": str(citation.url) if citation.url else None,
                    "citation": citation.model_dump(mode="json"),
                }
            )

        return {
            "query": question,
            "results": normalized_results,
            "raw": payload,
        }

