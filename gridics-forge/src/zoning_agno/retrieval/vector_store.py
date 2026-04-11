from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from zoning_agno.db.models import LegalChunkEmbeddingORM, LegalChunkORM
from zoning_agno.retrieval.embedder import BaseEmbedder


@dataclass(slots=True)
class ChunkEmbeddingRow:
    legal_chunk_id: int
    chunk_text: str
    source_document_id: int


class VectorStore:
    def __init__(self, session: Session, embedder: BaseEmbedder) -> None:
        self.session = session
        self.embedder = embedder

    def pending_chunks(self, *, source_document_id: int | None = None, limit: int = 100) -> list[ChunkEmbeddingRow]:
        stmt: Select[tuple[LegalChunkORM]] = (
            select(LegalChunkORM)
            .outerjoin(LegalChunkEmbeddingORM, LegalChunkEmbeddingORM.legal_chunk_id == LegalChunkORM.id)
            .where(LegalChunkEmbeddingORM.id.is_(None))
            .order_by(LegalChunkORM.id)
            .limit(limit)
        )
        if source_document_id is not None:
            stmt = stmt.where(LegalChunkORM.source_document_id == source_document_id)
        rows = self.session.scalars(stmt).all()
        return [
            ChunkEmbeddingRow(
                legal_chunk_id=row.id,
                chunk_text=row.chunk_text,
                source_document_id=row.source_document_id,
            )
            for row in rows
        ]

    def pending_chunk_count(self, *, source_document_id: int | None = None) -> int:
        stmt = (
            select(LegalChunkORM.id)
            .outerjoin(LegalChunkEmbeddingORM, LegalChunkEmbeddingORM.legal_chunk_id == LegalChunkORM.id)
            .where(LegalChunkEmbeddingORM.id.is_(None))
        )
        if source_document_id is not None:
            stmt = stmt.where(LegalChunkORM.source_document_id == source_document_id)
        return len(self.session.scalars(stmt).all())

    def upsert_embeddings(self, rows: list[ChunkEmbeddingRow]) -> int:
        if not rows:
            return 0
        embeddings = self.embedder.embed_texts([row.chunk_text for row in rows])
        by_chunk_id = {
            record.legal_chunk_id: record
            for record in self.session.scalars(
                select(LegalChunkEmbeddingORM).where(
                    LegalChunkEmbeddingORM.legal_chunk_id.in_([row.legal_chunk_id for row in rows])
                )
            ).all()
        }
        for row, embedding in zip(rows, embeddings, strict=False):
            existing = by_chunk_id.get(row.legal_chunk_id)
            if existing is None:
                self.session.add(
                    LegalChunkEmbeddingORM(
                        legal_chunk_id=row.legal_chunk_id,
                        embedding=embedding,
                        embedding_model=self.embedder.model_name,
                    )
                )
            else:
                existing.embedding = embedding
                existing.embedding_model = self.embedder.model_name
                self.session.add(existing)
        self.session.commit()
        return len(rows)

    def embed_pending_chunks(
        self,
        *,
        source_document_id: int | None = None,
        limit: int | None = None,
        batch_size: int = 32,
    ) -> int:
        total = 0
        while limit is None or total < limit:
            rows = self.pending_chunks(
                source_document_id=source_document_id,
                limit=batch_size if limit is None else min(batch_size, max(limit - total, 0)),
            )
            if not rows:
                break
            total += self.upsert_embeddings(rows)
        return total
