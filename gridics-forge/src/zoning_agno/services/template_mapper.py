from __future__ import annotations

from zoning_agno.schemas import AtomicFactBundle, CellPopulation, SheetPopulationBundle, TemplateSheet
from zoning_agno.services.fact_normalizer import (
    normalize_district_code_for_template,
    normalize_fact_field_name_for_template,
    normalize_permission_value,
    normalize_value_for_template,
)


def map_general_facts_to_template_rows(template_sheet: TemplateSheet, facts: AtomicFactBundle) -> SheetPopulationBundle:
    """Map dimensional facts onto existing Zones - General template rows by DB field name."""
    valid_row_keys = {row.key for row in template_sheet.rows}
    row_by_key = {row.key: row for row in template_sheet.rows}
    district_headers = template_sheet.header.district_headers
    populated_cells: list[CellPopulation] = []
    for fact in facts.facts:
        if fact.fact_type != "dimensional_standard":
            continue
        row_key = normalize_fact_field_name_for_template(template_sheet.sheet_name, fact, template_sheet)
        district_code = normalize_district_code_for_template(fact.district_code, district_headers)
        value = normalize_value_for_template(
            template_sheet.sheet_name,
            row_key or fact.field_name or "",
            fact.value_numeric if fact.value_numeric is not None else fact.value_text,
        )
        if row_key is None or row_key not in valid_row_keys or district_code is None or value in (None, ""):
            continue
        template_row = row_by_key[row_key]
        prefilled_districts = {
            header
            for header in district_headers
            if template_row.raw_values.get(header) not in (None, "")
        }
        if prefilled_districts and district_code not in prefilled_districts:
            continue
        populated_cells.append(
            CellPopulation(
                sheet_name=template_sheet.sheet_name,
                row_key=row_key,
                district_code=district_code,
                value=value,
                citations=fact.citations,
                confidence=fact.confidence,
                source_fact_ids=[fact.fact_id],
                requires_human_review=fact.requires_human_review,
            )
        )
    return SheetPopulationBundle(
        sheet_name=template_sheet.sheet_name,
        row_keys=[row.key for row in template_sheet.rows],
        district_codes=district_headers,
        populated_cells=populated_cells,
    )


def map_use_facts_to_template_rows(template_sheet: TemplateSheet, facts: AtomicFactBundle) -> SheetPopulationBundle:
    valid_row_keys = {row.key for row in template_sheet.rows}
    district_headers = template_sheet.header.district_headers
    populated_cells: list[CellPopulation] = []
    for fact in facts.facts:
        if fact.fact_type != "use_permission":
            continue
        row_key = str((fact.value_json or {}).get("template_row_key") or "")
        district_code = normalize_district_code_for_template(fact.district_code, district_headers)
        value = normalize_permission_value(fact.value_text)
        if row_key not in valid_row_keys or district_code is None or value in (None, ""):
            continue
        populated_cells.append(
            CellPopulation(
                sheet_name=template_sheet.sheet_name,
                row_key=row_key,
                district_code=district_code,
                value=value,
                citations=fact.citations,
                confidence=fact.confidence,
                source_fact_ids=[fact.fact_id],
                requires_human_review=fact.requires_human_review,
            )
        )
    return SheetPopulationBundle(
        sheet_name=template_sheet.sheet_name,
        row_keys=[row.key for row in template_sheet.rows],
        district_codes=district_headers,
        populated_cells=populated_cells,
    )


def map_parking_facts_to_template_rows(template_sheet: TemplateSheet, facts: AtomicFactBundle) -> SheetPopulationBundle:
    return SheetPopulationBundle(sheet_name=template_sheet.sheet_name, row_keys=[row.key for row in template_sheet.rows], district_codes=template_sheet.header.district_headers, populated_cells=[])


def map_use_capacity_facts_to_template_rows(template_sheet: TemplateSheet, facts: AtomicFactBundle) -> SheetPopulationBundle:
    valid_row_keys = {row.key for row in template_sheet.rows}
    district_headers = template_sheet.header.district_headers
    populated_cells: list[CellPopulation] = []
    for fact in facts.facts:
        if fact.fact_type not in {"district_metadata", "dimensional_standard"}:
            continue
        row_key = normalize_fact_field_name_for_template(template_sheet.sheet_name, fact, template_sheet) or fact.field_name
        district_code = normalize_district_code_for_template(fact.district_code, district_headers)
        raw_value = fact.value_json.get("boolean_value") if fact.value_json and "boolean_value" in fact.value_json else (
            fact.value_numeric if fact.value_numeric is not None else fact.value_text
        )
        value = normalize_value_for_template(template_sheet.sheet_name, row_key or fact.field_name or "", raw_value)
        if row_key not in valid_row_keys or district_code is None or value in (None, ""):
            continue
        populated_cells.append(
            CellPopulation(
                sheet_name=template_sheet.sheet_name,
                row_key=row_key,
                district_code=district_code,
                value=value,
                citations=fact.citations,
                confidence=fact.confidence,
                source_fact_ids=[fact.fact_id],
                requires_human_review=fact.requires_human_review,
            )
        )
    return SheetPopulationBundle(
        sheet_name=template_sheet.sheet_name,
        row_keys=[row.key for row in template_sheet.rows],
        district_codes=district_headers,
        populated_cells=populated_cells,
    )


def map_bonus_facts_to_template_rows(template_sheet: TemplateSheet, facts: AtomicFactBundle) -> SheetPopulationBundle:
    return SheetPopulationBundle(sheet_name=template_sheet.sheet_name, row_keys=[row.key for row in template_sheet.rows], district_codes=template_sheet.header.district_headers, populated_cells=[])
