from __future__ import annotations

from zoning_agno.schemas import AtomicFactBundle, AtomicZoningFact, Citation, TemplateRow, TemplateSheet, TemplateSheetHeader
from zoning_agno.services.template_mapper import map_general_facts_to_template_rows


def test_map_general_facts_to_template_rows_matches_template_db_field_names() -> None:
    template_sheet = TemplateSheet(
        sheet_name="Zones - General",
        header=TemplateSheetHeader(
            sheet_name="Zones - General",
            fixed_headers=["Field Name", "DB Field Name", "Data Type"],
            district_headers=["GC", "RS-6"],
        ),
        rows=[
            TemplateRow(sheet_name="Zones - General", row_index=2, key="PrincipalMaxHeightFt", col_a="Principal Building Max. Height", col_b="PrincipalMaxHeightFt", col_c="float"),
            TemplateRow(sheet_name="Zones - General", row_index=3, key="LotAreaMin", col_a="Lot Area Minimum", col_b="LotAreaMin", col_c="float"),
        ],
    )
    facts = AtomicFactBundle(
        facts=[
            AtomicZoningFact(
                fact_id="fact-1",
                fact_type="dimensional_standard",
                district_code="GC",
                field_name="PrincipalMaxHeight",
                value_numeric=50,
                unit="ft",
                citations=[Citation(title="Section 1", quote="Maximum height in GC district is 50 feet.", confidence=0.8)],
            ),
            AtomicZoningFact(
                fact_id="fact-2",
                fact_type="dimensional_standard",
                district_code="RS-6",
                field_name="MinLotArea",
                value_numeric=6000,
                unit="sq_ft",
                citations=[Citation(title="Section 2", quote="Minimum lot area in RS-6 district is 6000 square feet.", confidence=0.8)],
            ),
        ]
    )

    bundle = map_general_facts_to_template_rows(template_sheet, facts)

    assert len(bundle.populated_cells) == 2
    first = bundle.populated_cells[0]
    second = bundle.populated_cells[1]
    assert first.row_key == "PrincipalMaxHeightFt"
    assert first.district_code == "GC"
    assert first.value == 50
    assert second.row_key == "LotAreaMin"
    assert second.district_code == "RS-6"
    assert second.value == 6000


def test_map_general_facts_to_template_rows_skips_blank_template_districts_when_row_is_prefilled() -> None:
    template_sheet = TemplateSheet(
        sheet_name="Zones - General",
        header=TemplateSheetHeader(
            sheet_name="Zones - General",
            fixed_headers=["Field Name", "DB Field Name", "Data Type"],
            district_headers=["AO", "GC", "GR"],
        ),
        rows=[
            TemplateRow(
                sheet_name="Zones - General",
                row_index=2,
                key="PrincipalMaxHeightFt",
                col_a="Principal Building Max. Height (Podium)",
                col_b="PrincipalMaxHeightFt",
                col_c="float",
                raw_values={
                    "Field Name": "Principal Building Max. Height (Podium)",
                    "DB Field Name": "PrincipalMaxHeightFt",
                    "Data Type": "float",
                    "AO": 45,
                    "GR": 40,
                },
            ),
        ],
    )
    facts = AtomicFactBundle(
        facts=[
            AtomicZoningFact(
                fact_id="fact-ao",
                fact_type="dimensional_standard",
                district_code="AO",
                field_name="PrincipalMaxHeight",
                value_numeric=45,
                citations=[],
            ),
            AtomicZoningFact(
                fact_id="fact-gc",
                fact_type="dimensional_standard",
                district_code="GC",
                field_name="PrincipalMaxHeight",
                value_numeric=40,
                citations=[],
            ),
            AtomicZoningFact(
                fact_id="fact-gr",
                fact_type="dimensional_standard",
                district_code="GR",
                field_name="PrincipalMaxHeight",
                value_numeric=40,
                citations=[],
            ),
        ]
    )

    bundle = map_general_facts_to_template_rows(template_sheet, facts)

    assert {(cell.district_code, cell.value) for cell in bundle.populated_cells} == {
        ("AO", 45),
        ("GR", 40),
    }
