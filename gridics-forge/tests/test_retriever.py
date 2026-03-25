from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from zoning_agno.db.base import Base
from zoning_agno.ingest.municode import ingest_workbook
from zoning_agno.retrieval import DeterministicEmbedder, VectorStore
from zoning_agno.retrieval.retriever import Retriever
from zoning_agno.schemas import SourceKind
from zoning_agno.services.normalization_service import normalize_source_document


def _write_workbook(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Sheet1"
    worksheet.append(["Url", "NodeId", "Title", "Subtitle", "Content"])
    worksheet.append(["https://example.com/1", "CH1", "Chapter 1", "General Provisions", ""])
    worksheet.append(["https://example.com/2", "DEF", "Definitions", "", '"Lot" means a parcel of land used as a building site.'])
    worksheet.append(
        [
            "https://example.com/3",
            "S1",
            "Sec. 1-1.",
            "Dimensional Standards",
            "Minimum lot area is 5,000 square feet. See Section 2.4.1.",
        ]
    )
    worksheet.append(
        [
            "https://example.com/4",
            "S2",
            "Sec. 1-2.",
            "Parking",
            "Parking shall be provided at one space per dwelling unit.",
        ]
    )
    worksheet.append(
        [
            "https://example.com/5",
            "S3",
            "Section 2.4.1",
            "Accessory Uses",
            "Accessory uses are permitted in residential districts.",
        ]
    )
    workbook.save(path)


def _build_retriever(tmp_path: Path) -> Retriever:
    workbook_path = tmp_path / "municode.xlsx"
    _write_workbook(workbook_path)
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = Session(engine)
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
    return Retriever(session, embedder, source_document_id=ingest_stats.source_document_id)


def test_keyword_search_ranks_matching_chunk_first(tmp_path: Path) -> None:
    retriever = _build_retriever(tmp_path)
    hits = retriever.keyword_search("minimum lot area", limit=3)
    assert hits
    assert "Minimum lot area" in hits[0].chunk_text


def test_retrieve_definition_returns_exact_definition_hit(tmp_path: Path) -> None:
    retriever = _build_retriever(tmp_path)
    bundle = retriever.retrieve_definition("Lot")
    assert bundle.hits
    assert bundle.hits[0].retrieval_mode == "definition_exact"
    assert "parcel of land" in bundle.hits[0].chunk_text


def test_hybrid_retrieve_includes_expanded_context(tmp_path: Path) -> None:
    retriever = _build_retriever(tmp_path)
    bundle = retriever.hybrid_retrieve(query="minimum lot area")
    assert bundle.hits
    assert any(hit.retrieval_mode == "hybrid" for hit in bundle.hits)
    assert bundle.expanded_context


def test_retrieve_for_parking_prefers_parking_rule_chunks(tmp_path: Path) -> None:
    retriever = _build_retriever(tmp_path)
    bundle = retriever.retrieve_for_parking()
    assert bundle.hits
    assert bundle.hits[0].chunk_type == "parking_rule"
