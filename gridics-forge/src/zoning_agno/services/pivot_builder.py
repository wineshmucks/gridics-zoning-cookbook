from __future__ import annotations

from collections import defaultdict
from typing import Any

from zoning_agno.schemas import AtomicFactBundle, DistrictRegistryBundle, PivotRow, PivotTableBundle


def build_general_pivot_rows(district_registry: DistrictRegistryBundle, facts: AtomicFactBundle) -> PivotTableBundle:
    """Build the district-pivoted Zones - General sheet from atomic dimensional facts."""
    district_codes = [record.district_code for record in district_registry.districts]
    rows_by_key: dict[str, PivotRow] = {}
    for fact in facts.facts:
        if fact.fact_type != "dimensional_standard":
            continue
        row_key = fact.field_name or "UnknownField"
        row = rows_by_key.get(row_key)
        if row is None:
            row = PivotRow(
                output_sheet="Zones - General",
                row_key=row_key,
                row_label=row_key,
                row_metadata={},
                district_values={code: "" for code in district_codes},
                citations_by_district=defaultdict(list),  # type: ignore[arg-type]
            )
            rows_by_key[row_key] = row
        if fact.district_code:
            row.district_values.setdefault(fact.district_code, "")
            row.district_values[fact.district_code] = _fact_value(fact.value_numeric, fact.value_text)
            row.citations_by_district.setdefault(fact.district_code, []).extend(fact.citations)
        row.row_metadata.setdefault("units", {})
        if fact.district_code and fact.unit:
            row.row_metadata["units"][fact.district_code] = fact.unit
    ordered_rows = [rows_by_key[key] for key in sorted(rows_by_key)]
    return PivotTableBundle(sheet_name="Zones - General", district_codes=district_codes, rows=ordered_rows)


def build_use_pivot_rows(district_registry: DistrictRegistryBundle, facts: AtomicFactBundle) -> PivotTableBundle:
    """Placeholder for the next target; returns an empty uses pivot bundle."""
    return PivotTableBundle(sheet_name="Zones - Uses", district_codes=[record.district_code for record in district_registry.districts], rows=[])


def build_parking_pivot_rows(district_registry: DistrictRegistryBundle, facts: AtomicFactBundle) -> PivotTableBundle:
    """Placeholder for the next target; returns an empty parking pivot bundle."""
    return PivotTableBundle(sheet_name="Zones - Parking", district_codes=[record.district_code for record in district_registry.districts], rows=[])


def build_overlay_pivot_rows(district_registry: DistrictRegistryBundle, facts: AtomicFactBundle) -> PivotTableBundle:
    """Placeholder for the next target; returns an empty overlay pivot bundle."""
    return PivotTableBundle(sheet_name="Zones - Overlays", district_codes=[record.district_code for record in district_registry.districts], rows=[])


def _fact_value(value_numeric: float | None, value_text: str | None) -> Any:
    if value_numeric is not None and value_numeric.is_integer():
        return int(value_numeric)
    if value_numeric is not None:
        return value_numeric
    return value_text or ""
