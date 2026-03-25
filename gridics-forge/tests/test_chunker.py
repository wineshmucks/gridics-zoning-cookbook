from zoning_agno.normalize import chunk_sections
from zoning_agno.schemas import LegalSection


def test_chunk_sections_classifies_dimensional_and_parking_rules() -> None:
    sections = [
        LegalSection(
            id=1,
            source_document_id=1,
            node_id="S1",
            section_path="Chapter 1 > Sec. 1",
            title="Sec. 1.",
            subtitle="Dimensional Standards",
            body_text="Minimum lot area is 5,000 square feet.\n\nMaximum height is 35 feet.",
            section_type="section",
            parent_section_id=None,
        ),
        LegalSection(
            id=2,
            source_document_id=1,
            node_id="S2",
            section_path="Chapter 1 > Sec. 2",
            title="Sec. 2.",
            subtitle="Parking",
            body_text="Parking shall be provided at one space per dwelling unit.",
            section_type="section",
            parent_section_id=None,
        ),
    ]
    chunks = chunk_sections(sections, max_chars=80)
    assert chunks[0].chunk_type == "dimensional_rule"
    assert chunks[-1].chunk_type == "parking_rule"
    assert all(chunk.token_estimate for chunk in chunks)
