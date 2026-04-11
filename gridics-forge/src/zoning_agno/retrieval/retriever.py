from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import re
from typing import Iterable

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from zoning_agno.db.models import LegalChunkEmbeddingORM, LegalChunkORM, LegalCrossrefORM, LegalDefinitionORM, LegalSectionORM
from zoning_agno.retrieval.embedder import BaseEmbedder
from zoning_agno.schemas import RetrievalBundle, RetrievalHit


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _ChunkRecord:
    chunk_id: int
    legal_section_id: int
    source_document_id: int
    node_id: str | None
    title: str | None
    subtitle: str | None
    section_path: str | None
    chunk_type: str
    chunk_text: str
    metadata_json: dict[str, object]
    embedding: list[float] | None


class Retriever:
    """Retrieval-first service over normalized chunks, sections, definitions, and cross-references."""

    def __init__(self, session: Session, embedder: BaseEmbedder, source_document_id: int | None = None) -> None:
        self.session = session
        self.embedder = embedder
        self.source_document_id = source_document_id

    def retrieve_for_district(self, district_code: str, topic: str) -> RetrievalBundle:
        query = f"{district_code} {topic}".strip()
        return self.hybrid_retrieve(query=query, metadata_filters={"district_code": district_code})

    def retrieve_for_use(self, use_term: str, district_code: str | None = None) -> RetrievalBundle:
        query = f"{district_code or ''} {use_term} permitted conditional prohibited use".strip()
        filters = {"district_code": district_code} if district_code else None
        return self.hybrid_retrieve(query=query, metadata_filters=filters)

    def retrieve_for_field(self, field_name: str, district_code: str | None = None) -> RetrievalBundle:
        query = f"{district_code or ''} {field_name}".strip()
        filters = {"district_code": district_code} if district_code else None
        return self.hybrid_retrieve(query=query, metadata_filters=filters)

    def retrieve_for_parking(self, use_term: str | None = None, district_code: str | None = None) -> RetrievalBundle:
        query = " ".join(part for part in [district_code, use_term, "parking spaces requirements"] if part)
        filters = {"chunk_type": "parking_rule"}
        if district_code:
            filters["district_code"] = district_code
        return self.hybrid_retrieve(query=query or "parking", metadata_filters=filters)

    def retrieve_for_overlay(self, overlay_name: str) -> RetrievalBundle:
        return self.hybrid_retrieve(query=f"{overlay_name} overlay", metadata_filters={"overlay_name": overlay_name})

    def retrieve_definition(self, term: str) -> RetrievalBundle:
        definition_stmt = select(LegalDefinitionORM).where(LegalDefinitionORM.term.ilike(term))
        if self.source_document_id is not None:
            definition_stmt = definition_stmt.where(LegalDefinitionORM.source_document_id == self.source_document_id)
        exact = self.session.scalars(definition_stmt).all()
        hits: list[RetrievalHit] = []
        for definition in exact:
            section = self.session.get(LegalSectionORM, definition.section_id) if definition.section_id else None
            hits.append(
                RetrievalHit(
                    legal_chunk_id=None,
                    legal_section_id=definition.section_id,
                    node_id=definition.node_id,
                    title=section.title if section else term,
                    subtitle=section.subtitle if section else None,
                    section_path=section.section_path if section else None,
                    chunk_type="definition",
                    chunk_text=definition.definition_text,
                    score=1.0,
                    retrieval_mode="definition_exact",
                    metadata={"term": definition.term},
                )
            )
        if hits:
            expanded = self._expand_hits(hits)
            return RetrievalBundle(query=term, hits=hits, expanded_context=expanded, metadata={"mode": "definition"})
        return self.hybrid_retrieve(query=f"{term} definition", metadata_filters={"chunk_type": "definition"})

    def exact_metadata_filter(self, **filters: str | None) -> list[RetrievalHit]:
        logger.info(
            "RETRIEVE metadata_filter | source_document_id=%s filters=%s",
            self.source_document_id,
            {key: value for key, value in filters.items() if value not in (None, "")},
        )
        records = self._fetch_chunk_records()
        matched = [record for record in records if self._matches_metadata(record, filters)]
        hits = [self._record_to_hit(record, score=1.0, retrieval_mode="metadata") for record in matched]
        self._log_result_summary("metadata_filter", query=None, hits=hits)
        return hits

    def keyword_search(self, query: str, *, metadata_filters: dict[str, str | None] | None = None, limit: int = 10) -> list[RetrievalHit]:
        logger.info(
            "RETRIEVE keyword_search | source_document_id=%s query=%r limit=%s filters=%s",
            self.source_document_id,
            query,
            limit,
            metadata_filters or {},
        )
        records = self._fetch_chunk_records(query=query)
        scored = self._score_keyword_hits(records, query=query, metadata_filters=metadata_filters)
        hits = scored[:limit]
        self._log_result_summary("keyword_search", query=query, hits=hits)
        return hits

    def vector_search(self, query: str, *, metadata_filters: dict[str, str | None] | None = None, limit: int = 10) -> list[RetrievalHit]:
        logger.info(
            "RETRIEVE vector_search | source_document_id=%s query=%r limit=%s filters=%s",
            self.source_document_id,
            query,
            limit,
            metadata_filters or {},
        )
        logger.info(
            "EMBED query | provider=%s model=%s chars=%s preview=%r",
            self.embedder.__class__.__name__,
            self.embedder.model_name,
            len(query),
            self._truncate(query, 120),
        )
        query_embedding = self.embedder.embed_texts([query])[0]
        records = self._fetch_chunk_records(with_embeddings=True)
        scored: list[tuple[_ChunkRecord, float]] = []
        for record in records:
            if not self._matches_metadata(record, metadata_filters):
                continue
            if not record.embedding:
                continue
            scored.append((record, self._cosine_similarity(query_embedding, record.embedding)))
        scored.sort(key=lambda item: item[1], reverse=True)
        hits = [self._record_to_hit(record, score=score, retrieval_mode="vector") for record, score in scored[:limit]]
        logger.info(
            "VECTOR stats | source_document_id=%s candidate_count=%s embedded_candidates=%s returned=%s",
            self.source_document_id,
            len(records),
            len(scored),
            len(hits),
        )
        self._log_result_summary("vector_search", query=query, hits=hits)
        return hits

    def hybrid_retrieve(
        self,
        *,
        query: str,
        metadata_filters: dict[str, str | None] | None = None,
        limit: int = 10,
        expand_limit: int = 8,
    ) -> RetrievalBundle:
        logger.info(
            "RETRIEVE hybrid_start | source_document_id=%s query=%r limit=%s expand_limit=%s filters=%s",
            self.source_document_id,
            query,
            limit,
            expand_limit,
            metadata_filters or {},
        )
        keyword_hits = self.keyword_search(query, metadata_filters=metadata_filters, limit=max(limit * 2, limit))
        vector_hits = self.vector_search(query, metadata_filters=metadata_filters, limit=max(limit * 2, limit))

        combined: dict[tuple[int | None, int | None], RetrievalHit] = {}
        keyword_ranks = {self._hit_key(hit): index for index, hit in enumerate(keyword_hits, start=1)}
        vector_ranks = {self._hit_key(hit): index for index, hit in enumerate(vector_hits, start=1)}
        for hit in keyword_hits + vector_hits:
            key = self._hit_key(hit)
            if key not in combined:
                combined[key] = hit.model_copy(update={"retrieval_mode": "hybrid"})
        reranked: list[RetrievalHit] = []
        for key, hit in combined.items():
            keyword_rank = keyword_ranks.get(key)
            vector_rank = vector_ranks.get(key)
            score = 0.0
            if keyword_rank is not None:
                score += 1.0 / (keyword_rank + 1)
            if vector_rank is not None:
                score += 1.0 / (vector_rank + 1)
            reranked.append(hit.model_copy(update={"score": score}))
        reranked.sort(key=lambda item: item.score, reverse=True)
        top_hits = reranked[:limit]
        expanded = self._expand_hits(top_hits)[:expand_limit]
        bundle = RetrievalBundle(
            query=query,
            hits=top_hits,
            expanded_context=expanded,
            metadata={
                "mode": "hybrid",
                "keyword_hits": len(keyword_hits),
                "vector_hits": len(vector_hits),
                "source_document_id": self.source_document_id,
            },
        )
        logger.info(
            "RETRIEVE hybrid_complete | source_document_id=%s query=%r keyword_hits=%s vector_hits=%s top_hits=%s expanded=%s",
            self.source_document_id,
            query,
            len(keyword_hits),
            len(vector_hits),
            len(bundle.hits),
            len(bundle.expanded_context),
        )
        self._log_result_summary("hybrid_hits", query=query, hits=bundle.hits)
        self._log_result_summary("hybrid_expanded", query=query, hits=bundle.expanded_context)
        return bundle

    def _fetch_chunk_records(self, query: str | None = None, with_embeddings: bool = False) -> list[_ChunkRecord]:
        stmt: Select = (
            select(LegalChunkORM, LegalChunkEmbeddingORM)
            .outerjoin(LegalChunkEmbeddingORM, LegalChunkEmbeddingORM.legal_chunk_id == LegalChunkORM.id)
            .order_by(LegalChunkORM.id)
        )
        if self.source_document_id is not None:
            stmt = stmt.where(LegalChunkORM.source_document_id == self.source_document_id)
        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(
                    LegalChunkORM.title.ilike(like),
                    LegalChunkORM.subtitle.ilike(like),
                    LegalChunkORM.section_path.ilike(like),
                    LegalChunkORM.chunk_text.ilike(like),
                )
            )
        rows = self.session.execute(stmt).all()
        records = [
            _ChunkRecord(
                chunk_id=chunk.id,
                legal_section_id=chunk.legal_section_id,
                source_document_id=chunk.source_document_id,
                node_id=chunk.node_id,
                title=chunk.title,
                subtitle=chunk.subtitle,
                section_path=chunk.section_path,
                chunk_type=chunk.chunk_type,
                chunk_text=chunk.chunk_text,
                metadata_json=chunk.metadata_json or {},
                embedding=(list(embedding.embedding) if embedding and embedding.embedding is not None else None),
            )
            for chunk, embedding in rows
        ]
        if with_embeddings:
            return records
        return records

    def _score_keyword_hits(
        self,
        records: Iterable[_ChunkRecord],
        *,
        query: str,
        metadata_filters: dict[str, str | None] | None = None,
    ) -> list[RetrievalHit]:
        tokens = [token for token in re.findall(r"[A-Za-z0-9_.-]+", query.lower()) if token]
        scored: list[tuple[_ChunkRecord, float]] = []
        for record in records:
            if not self._matches_metadata(record, metadata_filters):
                continue
            haystack = " ".join(filter(None, [record.title, record.subtitle, record.section_path, record.chunk_text])).lower()
            if not tokens:
                continue
            score = 0.0
            for token in tokens:
                if token in (record.title or "").lower():
                    score += 2.5
                if token in (record.subtitle or "").lower():
                    score += 2.0
                if token in (record.section_path or "").lower():
                    score += 1.5
                if token in haystack:
                    score += 1.0
            if score > 0:
                scored.append((record, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [self._record_to_hit(record, score=score, retrieval_mode="keyword") for record, score in scored]

    def _matches_metadata(self, record: _ChunkRecord, filters: dict[str, str | None] | None) -> bool:
        if not filters:
            return True
        for key, value in filters.items():
            if value in (None, ""):
                continue
            normalized = str(value).lower()
            if key == "chunk_type":
                if normalized != (record.chunk_type or "").lower():
                    return False
                continue
            fields = [record.title or "", record.subtitle or "", record.section_path or "", record.chunk_text or ""]
            metadata_value = record.metadata_json.get(key)
            if metadata_value is not None:
                fields.append(str(metadata_value))
            if not any(normalized in field.lower() for field in fields):
                return False
        return True

    def _expand_hits(self, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        expanded: dict[tuple[int | None, int | None], RetrievalHit] = {}
        for hit in hits:
            section = self.session.get(LegalSectionORM, hit.legal_section_id) if hit.legal_section_id else None
            if section and section.parent_section_id:
                parent = self.session.get(LegalSectionORM, section.parent_section_id)
                if parent:
                    expanded[self._hit_key_from_ids(None, parent.id)] = RetrievalHit(
                        legal_chunk_id=None,
                        legal_section_id=parent.id,
                        node_id=parent.node_id,
                        title=parent.title,
                        subtitle=parent.subtitle,
                        section_path=parent.section_path,
                        chunk_type=parent.section_type,
                        chunk_text=parent.body_text,
                        score=0.5,
                        retrieval_mode="parent_expansion",
                        metadata={},
                    )
            if hit.legal_section_id:
                sibling_stmt = (
                    select(LegalChunkORM)
                    .where(LegalChunkORM.legal_section_id == hit.legal_section_id, LegalChunkORM.id != hit.legal_chunk_id)
                    .order_by(LegalChunkORM.chunk_index)
                    .limit(2)
                )
                for sibling in self.session.scalars(sibling_stmt).all():
                    expanded[self._hit_key_from_ids(sibling.id, sibling.legal_section_id)] = self._record_to_hit(
                        _ChunkRecord(
                            chunk_id=sibling.id,
                            legal_section_id=sibling.legal_section_id,
                            source_document_id=sibling.source_document_id,
                            node_id=sibling.node_id,
                            title=sibling.title,
                            subtitle=sibling.subtitle,
                            section_path=sibling.section_path,
                            chunk_type=sibling.chunk_type,
                            chunk_text=sibling.chunk_text,
                            metadata_json=sibling.metadata_json or {},
                            embedding=None,
                        ),
                        score=0.4,
                        retrieval_mode="sibling_expansion",
                    )
                crossrefs = self.session.scalars(
                    select(LegalCrossrefORM).where(LegalCrossrefORM.from_section_id == hit.legal_section_id).limit(3)
                ).all()
                for crossref in crossrefs:
                    target = self._resolve_crossref_target(crossref)
                    if target is not None:
                        expanded[self._hit_key_from_ids(None, target.id)] = RetrievalHit(
                            legal_chunk_id=None,
                            legal_section_id=target.id,
                            node_id=target.node_id,
                            title=target.title,
                            subtitle=target.subtitle,
                            section_path=target.section_path,
                            chunk_type=target.section_type,
                            chunk_text=target.body_text,
                            score=0.3,
                            retrieval_mode="crossref_expansion",
                            metadata={"ref_text": crossref.ref_text},
                        )
        for hit in hits:
            expanded.pop(self._hit_key(hit), None)
        return list(expanded.values())

    def _resolve_crossref_target(self, crossref: LegalCrossrefORM) -> LegalSectionORM | None:
        if crossref.to_section_id:
            return self.session.get(LegalSectionORM, crossref.to_section_id)
        stmt = select(LegalSectionORM)
        if self.source_document_id is not None:
            stmt = stmt.where(LegalSectionORM.source_document_id == self.source_document_id)
        ref = crossref.to_section_ref.lower()
        stmt = stmt.where(
            or_(
                LegalSectionORM.title.ilike(f"%{ref}%"),
                LegalSectionORM.subtitle.ilike(f"%{ref}%"),
                LegalSectionORM.section_path.ilike(f"%{ref}%"),
            )
        ).limit(1)
        return self.session.scalar(stmt)

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right, strict=False))
        left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
        right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
        return numerator / (left_norm * right_norm)

    @staticmethod
    def _record_to_hit(record: _ChunkRecord, *, score: float, retrieval_mode: str) -> RetrievalHit:
        return RetrievalHit(
            legal_chunk_id=record.chunk_id,
            legal_section_id=record.legal_section_id,
            node_id=record.node_id,
            title=record.title,
            subtitle=record.subtitle,
            section_path=record.section_path,
            chunk_type=record.chunk_type,
            chunk_text=record.chunk_text,
            score=score,
            retrieval_mode=retrieval_mode,
            metadata=record.metadata_json,
        )

    @staticmethod
    def _hit_key(hit: RetrievalHit) -> tuple[int | None, int | None]:
        return (hit.legal_chunk_id, hit.legal_section_id)

    @staticmethod
    def _hit_key_from_ids(chunk_id: int | None, section_id: int | None) -> tuple[int | None, int | None]:
        return (chunk_id, section_id)

    def _log_result_summary(self, operation: str, *, query: str | None, hits: list[RetrievalHit]) -> None:
        if not hits:
            logger.info(
                "RETRIEVE %s results | source_document_id=%s query=%r returned=0",
                operation,
                self.source_document_id,
                query,
            )
            return
        top = hits[:3]
        summary = [
            {
                "chunk_id": hit.legal_chunk_id,
                "section_id": hit.legal_section_id,
                "score": round(hit.score, 4),
                "chunk_type": hit.chunk_type,
                "title": self._truncate(hit.title or hit.section_path or "<untitled>", 80),
                "text_preview": self._truncate(hit.chunk_text, 120),
            }
            for hit in top
        ]
        logger.info(
            "RETRIEVE %s results | source_document_id=%s query=%r returned=%s top=%s",
            operation,
            self.source_document_id,
            query,
            len(hits),
            summary,
        )

    @staticmethod
    def _truncate(value: str | None, limit: int) -> str:
        text = (value or "").strip()
        if len(text) <= limit:
            return text
        return text[: limit - 3].rstrip() + "..."
