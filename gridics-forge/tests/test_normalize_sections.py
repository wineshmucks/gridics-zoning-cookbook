from zoning_agno.normalize import normalize_sections
from zoning_agno.schemas import MuniNode


def test_normalize_sections_builds_hierarchy() -> None:
    nodes = [
        MuniNode(row_number=2, node_id="CH1", title="Chapter 1", subtitle="General Provisions", content=""),
        MuniNode(row_number=3, node_id="AR1", title="Article I", subtitle="Administration", content=""),
        MuniNode(row_number=4, node_id="S1", title="Sec. 1-1.", subtitle="Purpose", content="This section explains purpose."),
        MuniNode(row_number=5, node_id="S2", title="Sec. 1-2.", subtitle="Applicability", content="See Section 2.4.1."),
    ]

    sections = normalize_sections(nodes, source_document_id=9)

    assert len(sections) == 4
    assert sections[0].section_type == "chapter"
    assert sections[2].section_path == "Chapter 1 - General Provisions > Article I - Administration > Sec. 1-1. - Purpose"
    assert sections[2].source_document_id == 9


def test_normalize_sections_skips_empty_rows() -> None:
    nodes = [MuniNode(row_number=2, node_id="A", title=None, subtitle=None, content=None)]
    assert normalize_sections(nodes) == []
