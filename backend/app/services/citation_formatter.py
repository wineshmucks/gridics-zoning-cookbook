"""Helpers to create deterministic citations from evidence payloads."""

from __future__ import annotations

from typing import Any

from app.schemas.citations import Citation


def build_property_citation(
    *,
    citation_id: str,
    label: str,
    address: str | None,
    metadata: dict[str, Any] | None = None,
) -> Citation:
    excerpt = f"Gridics property data for {address}" if address else "Gridics property data"
    return Citation(
        id=citation_id,
        source_type="gridics_property",
        label=label,
        excerpt=excerpt,
        metadata={k: v for k, v in (metadata or {}).items() if isinstance(v, (str, int, float, bool)) or v is None},
    )


def build_knowledge_citation(
    *,
    citation_id: str,
    label: str,
    section: str | None,
    excerpt: str | None,
    url: str | None,
    metadata: dict[str, Any] | None = None,
) -> Citation:
    filtered_metadata = {
        k: v
        for k, v in (metadata or {}).items()
        if isinstance(v, (str, int, float, bool)) or v is None
    }
    return Citation(
        id=citation_id,
        source_type="zoning_code",
        label=label,
        section=section,
        excerpt=excerpt,
        url=url,
        metadata=filtered_metadata,
    )


def render_references(citations: list[Citation]) -> list[str]:
    """Render references into short, deterministic bullet strings."""

    rendered: list[str] = []
    for citation in citations:
        base = citation.label
        if citation.section:
            base = f"{base}: {citation.section}"
        if citation.url:
            base = f"{base} ({citation.url})"
        rendered.append(base)
    return rendered

