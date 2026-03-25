from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from zoning_agno.db.base import Base
from zoning_agno.ingest.municode import ingest_workbook
from zoning_agno.retrieval import DeterministicEmbedder, Retriever, VectorStore
from zoning_agno.schemas import SourceKind
from zoning_agno.services.normalization_service import normalize_source_document
from zoning_agno.services.retrieval_context_service import RetrievalContextService


def _write_workbook(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Sheet1"
    worksheet.append(["Url", "NodeId", "Title", "Subtitle", "Content"])
    worksheet.append(["https://example.com/1", "CH1", "Chapter 1", "General Provisions", ""])
    worksheet.append(["https://example.com/2", "S1", "Sec. 1-1.", "Parking", "Parking shall be provided at one space per dwelling unit."])
    worksheet.append(["https://example.com/3", "S2", "Definitions", "", '"Lot" means a parcel of land used as a building site.'])
    workbook.save(path)


def test_retrieval_context_service_builds_family_bundles(tmp_path: Path) -> None:
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
        embedder = DeterministicEmbedder(dimensions=8)
        VectorStore(session, embedder).embed_pending_chunks(source_document_id=ingest_stats.source_document_id, limit=None, batch_size=8)
        retriever = Retriever(session, embedder, source_document_id=ingest_stats.source_document_id)
        context = RetrievalContextService(session, retriever, ingest_stats.source_document_id).build_context()

        assert context["source_document_id"] == ingest_stats.source_document_id
        assert context["districts"]["query"]
        assert context["uses"]["hits"] is not None
        assert context["parking"]["hits"] is not None
