from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from zoning_agno.config import Settings, get_settings
from zoning_agno.db.models import MuniNodeORM, SourceDocumentORM


def get_supplemental_source_urls(
    session: Session,
    source_document_id: int,
    *,
    settings: Settings | None = None,
) -> list[str]:
    """Return document-level supplemental sources without assuming a specific ingest format.

    Current schema still stores raw Municode rows in ``muni_nodes``. This helper keeps that
    compatibility detail isolated so extraction code can depend on a generic supplemental-source
    contract instead of a Municode-specific table.
    """
    resolved_settings = settings or get_settings()
    urls: list[str] = []
    source_document = session.get(SourceDocumentORM, source_document_id)
    if source_document is not None and _looks_like_pdf_source(source_document.source_url):
        urls.append(str(source_document.source_url))
    urls.extend(resolved_settings.supplemental_source_urls)
    urls.extend(_raw_node_supplemental_sources(session, source_document_id))
    return _dedupe(urls)


def _raw_node_supplemental_sources(session: Session, source_document_id: int) -> list[str]:
    urls: list[str] = []
    nodes = session.scalars(select(MuniNodeORM).where(MuniNodeORM.source_document_id == source_document_id)).all()
    for node in nodes:
        payload = node.raw_payload_json or {}
        overflow = payload.get("overflow_resolution") or {}
        source = str(overflow.get("source") or "")
        if source.startswith("pdf:"):
            urls.append(source[4:].split("#page=", 1)[0])
        supplemental = payload.get("supplemental_sources") or []
        if isinstance(supplemental, list):
            urls.extend(str(item) for item in supplemental if _looks_like_pdf_source(str(item)))
    return urls


def _looks_like_pdf_source(value: str | None) -> bool:
    if not value:
        return False
    return bool(
        re.search(r"\.pdf(?:$|\?)", value, re.IGNORECASE)
        or re.search(r"/DocumentCenter/View/.+PDF", value, re.IGNORECASE)
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered
