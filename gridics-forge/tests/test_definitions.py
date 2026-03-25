from zoning_agno.normalize import extract_definitions
from zoning_agno.schemas import LegalSection


def test_extract_definitions_reads_definition_sections() -> None:
    sections = [
        LegalSection(
            id=11,
            source_document_id=7,
            node_id="DEF1",
            section_path="Chapter 1 > Definitions",
            title="Definitions",
            subtitle=None,
            body_text='"Lot" means a parcel of land.\nDwelling Unit means one or more rooms for living.',
            section_type="section",
            parent_section_id=None,
        )
    ]
    definitions = extract_definitions(sections)
    assert [item["term"] for item in definitions] == ["Lot", "Dwelling Unit"]
    assert definitions[0]["section_id"] == 11
