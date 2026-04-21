"""Agno-friendly zoning knowledge retrieval tool."""

from __future__ import annotations

from typing import Any

from app.services.zoning_knowledge_tool_service import ZoningKnowledgeLookupService


def retrieve_zoning_knowledge(
    jurisdiction_id: str,
    question: str,
    limit: int = 5,
    service: ZoningKnowledgeLookupService | None = None,
) -> dict[str, Any]:
    """Return authoritative zoning knowledge snippets for a jurisdiction."""

    resolver = service or ZoningKnowledgeLookupService()
    result = resolver.retrieve(
        jurisdiction_id=jurisdiction_id,
        question=question,
        limit=limit,
    )
    return result

