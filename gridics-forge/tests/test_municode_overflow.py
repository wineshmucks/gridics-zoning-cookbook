from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from zoning_agno.db.base import Base
from zoning_agno.db.models import MuniNodeORM, SourceDocumentORM
from zoning_agno.services.municode_overflow import (
    OVERFLOW_PLACEHOLDER,
    find_best_supplemental_text,
    resolve_overflow_nodes,
)


def test_find_best_supplemental_text_prefers_matching_subtitle() -> None:
    match = find_best_supplemental_text(
        [
            ("pdf:a#page=1", "intro"),
            ("pdf:a#page=2", "Section 2.4.2.1 The Land Use Matrix AO RS-6 Accessory Dwelling Unit P NP PC-2"),
            ("pdf:a#page=3", "continued matrix rows Accessory Commercial Unit Medical Office"),
            ("pdf:b#page=1", "Completely unrelated zoning narrative."),
        ],
        title="Section 2.4.2.1",
        subtitle="The Land Use Matrix",
        node_id="PTIIIAPANDECO_CH2ZORE_ART4USRE_DIV2LAUSMA_S2.4.2.1THLAUSMA",
    )

    assert match is not None
    assert match.source == "pdf:a#page=2"
    assert "Land Use Matrix" in match.text
    assert "Accessory Commercial Unit" in match.text


def test_resolve_overflow_nodes_updates_matching_rows(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = SourceDocumentORM(
            jurisdiction="Abilene, TX",
            source_type="municode",
            source_file_name="source.xlsx",
            source_url="https://library.municode.com/tx/abilene/codes/code_of_ordinances",
        )
        session.add(source)
        session.flush()
        session.add(
            MuniNodeORM(
                source_document_id=source.id,
                row_number=10,
                node_id="PTIIIAPANDECO_CH2ZORE_ART4USRE_DIV2LAUSMA_S2.4.2.1THLAUSMA",
                url="https://library.municode.com/TX/Abilene/codes/Code_of_Ordinances?nodeId=PTIIIAPANDECO_CH2ZORE_ART4USRE_DIV2LAUSMA_S2.4.2.1THLAUSMA",
                title="Section 2.4.2.1",
                subtitle="The Land Use Matrix",
                content=OVERFLOW_PLACEHOLDER,
                raw_payload_json={},
            )
        )
        session.commit()

        monkeypatch.setattr(
            "zoning_agno.services.municode_overflow._fetch_municode_node_text",
            lambda url: None,
        )
        monkeypatch.setattr(
            "zoning_agno.services.municode_overflow._load_all_supplemental_pages",
            lambda sources: [
                (
                    "pdf:test#page=1",
                    "Section 2.4.2.1 The Land Use Matrix AO RS-6 Accessory Dwelling Unit P NP PC-2",
                )
            ],
        )

        stats = resolve_overflow_nodes(session, source.id, supplemental_sources=["test.pdf"])

        assert stats.overflow_node_count == 1
        assert stats.resolved_node_count == 1
        updated = session.scalar(select(MuniNodeORM))
        assert updated is not None
        assert updated.content is not None
        assert "Accessory Dwelling Unit" in updated.content
        assert updated.raw_payload_json["overflow_resolution"]["strategy"] == "pdf"
