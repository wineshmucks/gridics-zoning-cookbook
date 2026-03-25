from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from zoning_agno.db.base import Base
from zoning_agno.db.models import MuniNodeORM, SourceDocumentORM
from zoning_agno.ingest.municode import (
    build_muni_nodes,
    detect_primary_sheet,
    ingest_workbook,
    normalize_column_name,
)
from zoning_agno.schemas import SourceKind


def _write_workbook(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Export"
    worksheet.append(["Url", "NodeId", "Title", "Subtitle", "Content"])
    worksheet.append(["https://example.com/1", "100", "Article 1", "Intent", "Purpose text"])
    worksheet.append(["https://example.com/2", "101", "Section 1.1", "", "District content"])
    sparse = workbook.create_sheet("Notes")
    sparse.append(["Only", "Misc"])
    sparse.append(["foo", "bar"])
    workbook.save(path)


def test_normalize_column_name() -> None:
    assert normalize_column_name("NodeId") == "node_id"
    assert normalize_column_name("Source URL") == "source_url"


def test_detect_primary_sheet(tmp_path: Path) -> None:
    workbook_path = tmp_path / "municode.xlsx"
    _write_workbook(workbook_path)
    assert detect_primary_sheet(workbook_path) == "Export"


def test_build_muni_nodes_preserves_row_numbers() -> None:
    rows = [
        {"url": "https://example.com", "node_id": "A1", "title": "Title", "subtitle": None, "content": "Body"},
        {"url": None, "node_id": "A2", "title": "Title 2", "content": "Body 2"},
    ]
    nodes = build_muni_nodes(rows)
    assert [node.row_number for node in nodes] == [2, 3]
    assert nodes[0].raw_payload_json["node_id"] == "A1"


def test_build_muni_nodes_uses_original_workbook_row_number() -> None:
    rows = [
        {
            "_source_row_number": 5,
            "url": "https://example.com",
            "node_id": "A1",
            "title": "Title",
            "subtitle": None,
            "content": "Body",
        }
    ]
    nodes = build_muni_nodes(rows)
    assert nodes[0].row_number == 5


def test_ingest_workbook_loads_source_document_and_nodes(tmp_path: Path) -> None:
    workbook_path = tmp_path / "municode.xlsx"
    _write_workbook(workbook_path)

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        stats = ingest_workbook(
            session=session,
            workbook_path=workbook_path,
            jurisdiction="Abilene, TX",
            source_url="https://library.municode.com/tx/abilene",
            source_type=SourceKind.MUNICODE,
        )
        assert stats.row_count == 2
        assert stats.sheet_name == "Export"

        source_document = session.scalar(select(SourceDocumentORM))
        assert source_document is not None
        assert source_document.jurisdiction == "Abilene, TX"

        rows = session.scalars(select(MuniNodeORM).order_by(MuniNodeORM.row_number)).all()
        assert [row.node_id for row in rows] == ["100", "101"]
        assert rows[0].content == "Purpose text"
