from __future__ import annotations

from zoning_agno.schemas import AtomicFactBundle, AtomicZoningFact, Citation, TemplateRow, TemplateSheet, TemplateSheetHeader
from zoning_agno.services.template_mapper import map_use_capacity_facts_to_template_rows, map_use_facts_to_template_rows


def test_map_use_facts_to_template_rows_matches_existing_template_rows() -> None:
    template_sheet = TemplateSheet(
        sheet_name="Zones - Uses",
        header=TemplateSheetHeader(
            sheet_name="Zones - Uses",
            fixed_headers=["Uses Label Id", "Use Name", "Use Value"],
            district_headers=["AO", "GC"],
        ),
        rows=[
            TemplateRow(sheet_name="Zones - Uses", row_index=2, key="373379|Accessory Dwelling Unit|Use Allowance", col_a=373379, col_b="Accessory Dwelling Unit", col_c="Use Allowance"),
            TemplateRow(sheet_name="Zones - Uses", row_index=3, key="373379|Accessory Dwelling Unit|Use Limit", col_a=373379, col_b="Accessory Dwelling Unit", col_c="Use Limit"),
        ],
    )
    facts = AtomicFactBundle(
        facts=[
            AtomicZoningFact(
                fact_id="fact-use-1",
                fact_type="use_permission",
                district_code="AO",
                use_key="accessory_dwelling_unit",
                value_text="P",
                value_json={"template_row_key": "373379|Accessory Dwelling Unit|Use Allowance", "use_name": "Accessory Dwelling Unit"},
                citations=[Citation(title="Section 1", quote="Accessory dwelling units may otherwise be permitted.", confidence=0.8)],
            )
        ]
    )

    bundle = map_use_facts_to_template_rows(template_sheet, facts)

    assert len(bundle.populated_cells) == 1
    cell = bundle.populated_cells[0]
    assert cell.row_key == "373379|Accessory Dwelling Unit|Use Allowance"
    assert cell.district_code == "AO"
    assert cell.value == "P"


def test_map_use_facts_preserves_richer_permission_codes() -> None:
    template_sheet = TemplateSheet(
        sheet_name="Zones - Uses",
        header=TemplateSheetHeader(
            sheet_name="Zones - Uses",
            fixed_headers=["Uses Label Id", "Use Name", "Use Value"],
            district_headers=["GC"],
        ),
        rows=[
            TemplateRow(sheet_name="Zones - Uses", row_index=2, key="1|Accessory Commercial Unit|Use Allowance", col_a=1, col_b="Accessory Commercial Unit", col_c="Use Allowance"),
        ],
    )
    facts = AtomicFactBundle(
        facts=[
            AtomicZoningFact(
                fact_id="fact-use-pc2",
                fact_type="use_permission",
                district_code="GC",
                use_key="accessory_commercial_unit",
                value_text="PC-2",
                value_json={"template_row_key": "1|Accessory Commercial Unit|Use Allowance", "use_name": "Accessory Commercial Unit"},
                citations=[Citation(title="Section 1", quote="Accessory commercial unit is PC-2.", confidence=0.8)],
            )
        ]
    )

    bundle = map_use_facts_to_template_rows(template_sheet, facts)

    assert len(bundle.populated_cells) == 1
    assert bundle.populated_cells[0].value == "PC-2"


def test_map_use_capacity_facts_to_template_rows_accepts_district_metadata() -> None:
    template_sheet = TemplateSheet(
        sheet_name="Zones - Use Capacity",
        header=TemplateSheetHeader(
            sheet_name="Zones - Use Capacity",
            fixed_headers=["Field Name", "DB Field Name", "Data Type"],
            district_headers=["MF"],
        ),
        rows=[
            TemplateRow(sheet_name="Zones - Use Capacity", row_index=2, key="MaximumResidentialFAR", col_a="Maximum Residential FAR", col_b="MaximumResidentialFAR", col_c="float"),
            TemplateRow(sheet_name="Zones - Use Capacity", row_index=3, key="DensityUL", col_a="Residential Density UL", col_b="DensityUL", col_c="boolean"),
        ],
    )
    facts = AtomicFactBundle(
        facts=[
            AtomicZoningFact(
                fact_id="fact-capacity",
                fact_type="district_metadata",
                district_code="MF",
                field_name="MaximumResidentialFAR",
                value_numeric=24,
                citations=[Citation(title="Section 1", quote="maximum 24 units per gross acre", confidence=0.8)],
            ),
            AtomicZoningFact(
                fact_id="fact-density-ul",
                fact_type="district_metadata",
                district_code="MF",
                field_name="DensityUL",
                value_json={"boolean_value": True},
                value_text="true",
                citations=[Citation(title="Section 1", quote="maximum 24 units per gross acre", confidence=0.8)],
            ),
        ]
    )

    bundle = map_use_capacity_facts_to_template_rows(template_sheet, facts)

    assert [(cell.row_key, cell.value) for cell in bundle.populated_cells] == [
        ("MaximumResidentialFAR", 24),
        ("DensityUL", True),
    ]
