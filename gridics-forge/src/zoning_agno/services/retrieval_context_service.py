from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from zoning_agno.db.models import LegalChunkORM, LegalDefinitionORM, SourceDocumentORM
from zoning_agno.retrieval.retriever import Retriever


class RetrievalContextService:
    """Build deterministic retrieval bundles for downstream extraction and QA steps."""

    _PRIMARY_LIMITS = {
        "districts": 6,
        "uses": 6,
        "general_standards": 5,
        "parking": 5,
        "overlays": 4,
        "definitions": 4,
        "qa": 5,
    }
    _EXPANDED_LIMITS = {
        "districts": 3,
        "uses": 3,
        "general_standards": 2,
        "parking": 2,
        "overlays": 2,
        "definitions": 2,
        "qa": 2,
    }
    _TEXT_LIMITS = {
        "districts": 900,
        "uses": 900,
        "general_standards": 700,
        "parking": 700,
        "overlays": 700,
        "definitions": 600,
        "qa": 650,
    }

    def __init__(self, session: Session, retriever: Retriever, source_document_id: int) -> None:
        self.session = session
        self.retriever = retriever
        self.source_document_id = source_document_id

    def build_context(self) -> dict[str, object]:
        source_document = self.session.get(SourceDocumentORM, self.source_document_id)
        if source_document is None:
            raise ValueError(f"Source document not found: {self.source_document_id}")
        chunk_count = self.session.scalar(
            select(func.count()).select_from(LegalChunkORM).where(LegalChunkORM.source_document_id == self.source_document_id)
        )
        definition_count = self.session.scalar(
            select(func.count()).select_from(LegalDefinitionORM).where(LegalDefinitionORM.source_document_id == self.source_document_id)
        )
        raw_bundles = {
            "districts": self.retriever.hybrid_retrieve(query="zoning district base district overlay zone", limit=12).model_dump(),
            "uses": self.retriever.retrieve_for_use("permitted conditional prohibited accessory uses").model_dump(),
            "general_standards": self.retriever.hybrid_retrieve(
                query="minimum lot area width depth frontage setback height density far floor area ratio",
                limit=12,
            ).model_dump(),
            "parking": self.retriever.retrieve_for_parking().model_dump(),
            "overlays": self.retriever.retrieve_for_overlay("overlay").model_dump(),
            "definitions": self.retriever.hybrid_retrieve(query="definition defined term means shall mean", limit=8).model_dump(),
            "qa": self.retriever.hybrid_retrieve(query="district use parking dimensional standards citations ambiguity", limit=10).model_dump(),
        }
        return {
            "source_document_id": self.source_document_id,
            "source_metadata": {
                "jurisdiction": source_document.jurisdiction,
                "source_url": source_document.source_url,
                "source_file_name": source_document.source_file_name,
                "source_type": source_document.source_type,
                "chunk_count": chunk_count or 0,
                "definition_count": definition_count or 0,
            },
            "districts": raw_bundles["districts"],
            "uses": raw_bundles["uses"],
            "general_standards": raw_bundles["general_standards"],
            "parking": raw_bundles["parking"],
            "overlays": raw_bundles["overlays"],
            "definitions": raw_bundles["definitions"],
            "qa": raw_bundles["qa"],
            "llm_context": {
                name: self._compact_bundle(name, bundle)
                for name, bundle in raw_bundles.items()
            },
        }

    def _compact_bundle(self, name: str, bundle: dict[str, Any]) -> dict[str, Any]:
        primary_limit = self._PRIMARY_LIMITS.get(name, 5)
        expanded_limit = self._EXPANDED_LIMITS.get(name, 2)
        text_limit = self._TEXT_LIMITS.get(name, 700)
        return {
            "query": bundle.get("query"),
            "metadata": bundle.get("metadata") or {},
            "hit_count": len(bundle.get("hits") or []),
            "expanded_count": len(bundle.get("expanded_context") or []),
            "hits": [
                self._compact_hit(hit, text_limit=text_limit)
                for hit in (bundle.get("hits") or [])[:primary_limit]
            ],
            "expanded_context": [
                self._compact_hit(hit, text_limit=max(300, text_limit // 2))
                for hit in (bundle.get("expanded_context") or [])[:expanded_limit]
            ],
        }

    @staticmethod
    def _compact_hit(hit: dict[str, Any], *, text_limit: int) -> dict[str, Any]:
        metadata = dict(hit.get("metadata") or {})
        parent_title = metadata.get("parent_title")
        ref_text = metadata.get("ref_text")
        compact: dict[str, Any] = {
            "legal_chunk_id": hit.get("legal_chunk_id"),
            "legal_section_id": hit.get("legal_section_id"),
            "node_id": hit.get("node_id"),
            "title": hit.get("title"),
            "subtitle": hit.get("subtitle"),
            "section_path": hit.get("section_path"),
            "chunk_type": hit.get("chunk_type"),
            "score": hit.get("score"),
            "retrieval_mode": hit.get("retrieval_mode"),
            "chunk_text": RetrievalContextService._truncate_text(hit.get("chunk_text"), text_limit),
        }
        if parent_title:
            compact["parent_title"] = parent_title
        if ref_text:
            compact["ref_text"] = ref_text
        if metadata:
            compact["metadata"] = {
                key: value
                for key, value in metadata.items()
                if key in {"district_code", "overlay_name", "table_name", "term", "section_type", "parent_title", "ref_text"}
            }
        return compact

    @staticmethod
    def _truncate_text(value: Any, limit: int) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return text[: limit - 3].rstrip() + "..."
