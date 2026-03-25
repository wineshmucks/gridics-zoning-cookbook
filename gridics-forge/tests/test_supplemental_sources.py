from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from zoning_agno.db.base import Base
from zoning_agno.config import Settings
from zoning_agno.db.models import MuniNodeORM, SourceDocumentORM
from zoning_agno.schemas import SourceKind
from zoning_agno.services.supplemental_pdf_facts import _classify_standards_table
from zoning_agno.services.supplemental_sources import get_supplemental_source_urls


def test_get_supplemental_source_urls_is_generic_and_deduped(tmp_path: Path) -> None:
    settings = Settings(supplemental_source_urls=["https://example.com/zoning.pdf"])
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'test.db'}", future=True)
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, future=True)
    with SessionFactory() as session:
        source = SourceDocumentORM(
            jurisdiction="Anywhere",
            source_type=SourceKind.HTML.value,
            source_file_name="code.html",
            source_url="https://example.com/code.html",
        )
        session.add(source)
        session.flush()
        session.add(
            MuniNodeORM(
                source_document_id=source.id,
                row_number=1,
                node_id="n1",
                title="Section 1",
                subtitle="Test",
                content="Content is too large for cell.",
                raw_payload_json={
                    "overflow_resolution": {
                        "source": "pdf:https://example.com/zoning.pdf#page=40",
                    }
                },
            )
        )
        session.commit()
        urls = get_supplemental_source_urls(session, source.id, settings=settings)
    assert urls == ["https://example.com/zoning.pdf"]


def test_classify_standards_table_is_dynamic() -> None:
    residential_table = [
        ["Zoning\nDistrict", "Maximum\nDensity of\nDwelling\nUnits Per\nAcre", "Minimum Lot Size", None],
        [None, None, "Area\n(s.f.)", "Width\n(ft)"],
        ["AO", "n/a", "217,800", "200"],
    ]
    nonresidential_table = [
        ["ZONING\nDISTRICT", "", "MINIMUM", None, "MINIMUM BUILDING LINE SETBACKS", "MAXIMUM\nFLOOR\nAREA\nRATIO\n(FAR)"],
        [None, None, "LOT SIZE", None, None],
        ["CU", "60", "100", "none", None, "4:1"],
    ]
    assert _classify_standards_table(residential_table) == "residential_standards"
    assert _classify_standards_table(nonresidential_table) == "nonresidential_standards"
