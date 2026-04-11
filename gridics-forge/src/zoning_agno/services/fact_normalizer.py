from __future__ import annotations

import re

from zoning_agno.schemas import AtomicZoningFact, TemplateSheet


def normalize_permission_value(value: str | None) -> str | None:
    """Normalize raw permission labels into canonical Gridics-style values."""
    if value is None:
        return None
    normalized = value.strip().upper()
    if re.fullmatch(r"(?:P|NP|PC|SE)(?:-\d+)?", normalized):
        return normalized
    mapping = {
        "P": "P",
        "PERMITTED": "P",
        "ALLOWED": "P",
        "NP": "NP",
        "N": "NP",
        "NOT PERMITTED": "NP",
        "PROHIBITED": "NP",
        "PC": "PC",
        "C": "PC",
        "CONDITIONAL": "PC",
        "CONDITIONAL USE": "PC",
        "SPECIAL EXCEPTION": "SE",
        "SE": "SE",
    }
    return mapping.get(normalized, normalized or None)


def normalize_numeric_unit(value_text: str | None, unit_hint: str | None = None) -> tuple[float | None, str | None]:
    """Extract a numeric value and canonical unit from free text."""
    if not value_text:
        return None, unit_hint
    normalized = value_text.replace(",", "")
    match = re.search(r"(-?\d+(?:\.\d+)?)", normalized)
    value_numeric = float(match.group(1)) if match else None
    lowered = normalized.lower()
    unit = unit_hint
    if "square feet" in lowered or "sq. ft" in lowered or "sq ft" in lowered:
        unit = "sq_ft"
    elif re.search(r"\bfeet\b|\bfoot\b|\bft\b", lowered):
        unit = "ft"
    elif "%" in lowered:
        unit = "percent"
    return value_numeric, unit


def normalize_field_name(value: str | None) -> str | None:
    """Map source-facing dimensional labels into stable field names."""
    if not value:
        return None
    normalized = " ".join(value.strip().lower().split())
    mapping = {
        "minimum lot area": "MinLotArea",
        "lot area": "MinLotArea",
        "minimum lot width": "MinLotWidth",
        "lot width": "MinLotWidth",
        "minimum lot depth": "MinLotDepth",
        "lot depth": "MinLotDepth",
        "minimum frontage": "MinFrontage",
        "frontage": "MinFrontage",
        "maximum height": "PrincipalMaxHeight",
        "building height": "PrincipalMaxHeight",
        "height": "PrincipalMaxHeight",
        "front setback": "MinFrontSetback",
        "rear setback": "MinRearSetback",
        "side setback": "MinSideSetback",
        "minimum rear yard": "MinRearSetback",
        "minimum side yard": "MinSideSetback",
    }
    return mapping.get(normalized, "".join(part.capitalize() for part in re.split(r"[^a-z0-9]+", normalized) if part))


def normalize_use_key(value: str | None) -> str | None:
    """Collapse raw use labels into a deterministic snake_case key."""
    if not value:
        return None
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or None


def flag_ambiguous_fact(*, has_district_code: bool, has_field_name: bool, has_value: bool) -> bool:
    """Flag incomplete facts for review rather than dropping them."""
    return not (has_district_code and has_field_name and has_value)


def normalize_fact_field_name_for_template(
    sheet_name: str,
    fact: AtomicZoningFact,
    template_sheet: TemplateSheet,
) -> str | None:
    """Normalize an extracted fact field name to a template DB field name when possible."""
    field_name = fact.field_name
    if not field_name:
        return None
    template_fields = {str(row.col_b): str(row.col_b) for row in template_sheet.rows if row.col_b}
    aliases = {
        "PrincipalMaxHeight": ["PrincipalMaxHeightFt", "TowerMaxHeightFt"],
        "MinLotArea": ["LotAreaMin"],
        "MinLotWidth": ["LotWidthMin"],
        "MinFrontSetback": ["PFrontSetbackPrincipal", "OFrontSetbackPrincipal", "TFrontSetbackPrincipal"],
        "MinRearSetback": ["PRearSetback", "ORearSetback", "TRearSetback"],
        "MinSideSetback": ["PSideSetback", "OSideSetback", "TSideSetback"],
        "MinLotDepth": [],
        "DensityNet": ["DensityNet", "MaximumResidentialFAR"],
        "MaximumResidentialFAR": ["MaximumResidentialFAR"],
        "DensityUL": ["DensityUL"],
        "Minimum1DwellingUnit": ["Minimum1DwellingUnit"],
    }
    if field_name in template_fields:
        return template_fields[field_name]
    for candidate in aliases.get(field_name, []):
        if candidate in template_fields:
            return candidate
    normalized_lookup = _normalize_lookup(field_name)
    for template_field in template_fields:
        if _normalize_lookup(template_field) == normalized_lookup:
            return template_field
    return None


def normalize_district_code_for_template(district_code: str | None, template_districts: list[str]) -> str | None:
    """Normalize an extracted district code onto a canonical template district header."""
    if not district_code:
        return None
    normalized = _normalize_lookup(district_code)
    for header in template_districts:
        if _normalize_lookup(header) == normalized:
            return header
    aliases = {
        "PDCOR": "PD/COR",
    }
    alias = aliases.get(normalized)
    if alias in template_districts:
        return alias
    return None


def normalize_value_for_template(sheet_name: str, row_key: str, raw_value):
    """Normalize a raw extracted value into a template-compatible cell value."""
    if raw_value in (None, ""):
        return None
    return raw_value


def _normalize_lookup(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())
