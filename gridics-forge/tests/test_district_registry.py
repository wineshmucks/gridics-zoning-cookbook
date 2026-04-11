from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from zoning_agno.db.base import Base
from zoning_agno.ingest.municode import ingest_workbook
from zoning_agno.schemas import SourceKind
from zoning_agno.services.district_registry import (
    build_district_registry,
    extract_district_codes_from_text,
    extract_district_codes_from_titles,
    normalize_district_code,
)
from zoning_agno.services.normalization_service import normalize_source_document


def _write_workbook(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Sheet1"
    worksheet.append(["Url", "NodeId", "Title", "Subtitle", "Content"])
    worksheet.append(["https://example.com/1", "ART", "Residential Districts", "", "The RS-6 and RS-8 districts establish residential areas."])
    worksheet.append(["https://example.com/2", "GC", "GC - General Commercial District", "", "Maximum height in GC district is 50 feet."])
    worksheet.append(["https://example.com/3", "CBD", "CBD Central Business District", "", "CBD lots require a minimum lot area of 2,500 square feet."])
    workbook.save(path)


def test_normalize_district_code_normalizes_dash_and_case() -> None:
    assert normalize_district_code("rs–12") == "RS-12"


def test_extract_district_codes_helpers_find_expected_codes() -> None:
    assert extract_district_codes_from_titles(["GC - General Commercial District", "CBD Central Business District"]) == ["GC", "CBD"]
    assert extract_district_codes_from_text(["The RS-6 and RS-8 districts establish residential areas."]) == ["RS-6", "RS-8"]


def test_build_district_registry_collects_evidence_backed_codes(tmp_path: Path) -> None:
    workbook_path = tmp_path / "districts.xlsx"
    _write_workbook(workbook_path)
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ingest_stats = ingest_workbook(
            session=session,
            workbook_path=workbook_path,
            jurisdiction="Test City",
            source_url="https://example.com/source",
            source_type=SourceKind.MUNICODE,
        )
        normalize_source_document(session, ingest_stats.source_document_id)
        bundle = build_district_registry(session, ingest_stats.source_document_id)

    assert [record.district_code for record in bundle.districts] == ["RS-6", "RS-8", "GC", "CBD"]
    gc = next(record for record in bundle.districts if record.district_code == "GC")
    assert gc.district_name == "General Commercial District"
    assert gc.citations
