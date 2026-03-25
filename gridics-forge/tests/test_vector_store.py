from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from zoning_agno.db.base import Base
from zoning_agno.db.models import LegalChunkEmbeddingORM
from zoning_agno.ingest.municode import ingest_workbook
from zoning_agno.retrieval import DeterministicEmbedder, VectorStore
from zoning_agno.schemas import SourceKind
from zoning_agno.services.normalization_service import normalize_source_document


def _write_workbook(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Sheet1"
    worksheet.append(["Url", "NodeId", "Title", "Subtitle", "Content"])
    worksheet.append(["https://example.com/1", "S1", "Sec. 1-1.", "Purpose", "Minimum lot area is 5,000 square feet."])
    worksheet.append(["https://example.com/2", "S2", "Sec. 1-2.", "Parking", "Parking is one space per dwelling unit."])
    workbook.save(path)


def test_vector_store_embeds_pending_chunks(tmp_path: Path) -> None:
    workbook_path = tmp_path / "municode.xlsx"
    _write_workbook(workbook_path)
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        ingest_stats = ingest_workbook(
            session=session,
            workbook_path=workbook_path,
            jurisdiction="Test City",
            source_url="https://example.com",
            source_type=SourceKind.MUNICODE,
        )
        normalize_source_document(session, ingest_stats.source_document_id)

        store = VectorStore(session, DeterministicEmbedder(dimensions=8))
        embedded_count = store.embed_pending_chunks(source_document_id=ingest_stats.source_document_id, limit=10, batch_size=2)

        rows = session.scalars(select(LegalChunkEmbeddingORM)).all()
        assert embedded_count == len(rows)
        assert embedded_count >= 2
        assert len(rows[0].embedding) == 8
        assert rows[0].embedding_model == "deterministic-hash"


def test_vector_store_embeds_all_when_limit_is_none(tmp_path: Path) -> None:
    workbook_path = tmp_path / "municode.xlsx"
    _write_workbook(workbook_path)
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        ingest_stats = ingest_workbook(
            session=session,
            workbook_path=workbook_path,
            jurisdiction="Test City",
            source_url="https://example.com",
            source_type=SourceKind.MUNICODE,
        )
        normalize_source_document(session, ingest_stats.source_document_id)

        store = VectorStore(session, DeterministicEmbedder(dimensions=8))
        embedded_count = store.embed_pending_chunks(source_document_id=ingest_stats.source_document_id, limit=None, batch_size=1)

        assert embedded_count == 2
        assert store.pending_chunk_count(source_document_id=ingest_stats.source_document_id) == 0
