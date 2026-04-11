from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from zoning_agno.db.base import Base
from zoning_agno.db.models import LegalChunkORM, LegalCrossrefORM, LegalDefinitionORM, LegalSectionORM
from zoning_agno.ingest.municode import ingest_workbook
from zoning_agno.schemas import SourceKind
from zoning_agno.services.normalization_service import normalize_source_document


def _write_workbook(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Sheet1"
    worksheet.append([None, None, None, None, None])
    worksheet.append(["Url", "NodeId", "Title", "Subtitle", "Content"])
    worksheet.append(["https://example.com/1", "CH1", "Chapter 1", "General Provisions", ""])
    worksheet.append(["https://example.com/2", "S1", "Definitions", "", '"Lot" means a parcel of land.'])
    worksheet.append(["https://example.com/3", "S2", "Sec. 1-2.", "Parking", "See Section 2.4.1. Parking is one space per unit."])
    workbook.save(path)


def test_normalization_service_persists_outputs(tmp_path: Path) -> None:
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

        stats = normalize_source_document(session, ingest_stats.source_document_id)
        assert stats.section_count == 3

        sections = session.scalars(select(LegalSectionORM)).all()
        chunks = session.scalars(select(LegalChunkORM)).all()
        definitions = session.scalars(select(LegalDefinitionORM)).all()
        crossrefs = session.scalars(select(LegalCrossrefORM)).all()

        assert len(sections) == 3
        assert len(chunks) >= 2
        assert len(definitions) == 1
        assert len(crossrefs) == 1


def test_normalization_service_is_idempotent_for_same_source(tmp_path: Path) -> None:
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

        first = normalize_source_document(session, ingest_stats.source_document_id)
        second = normalize_source_document(session, ingest_stats.source_document_id)

        sections = session.scalars(select(LegalSectionORM)).all()
        chunks = session.scalars(select(LegalChunkORM)).all()
        definitions = session.scalars(select(LegalDefinitionORM)).all()
        crossrefs = session.scalars(select(LegalCrossrefORM)).all()

        assert first.section_count == second.section_count == 3
        assert len(sections) == 3
        assert len(chunks) == first.chunk_count
        assert len(definitions) == 1
        assert len(crossrefs) == 1
