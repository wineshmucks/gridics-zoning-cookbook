from __future__ import annotations

import re
from collections.abc import Iterable
from difflib import SequenceMatcher
from functools import lru_cache
from io import BytesIO
from typing import Any
from uuid import uuid4

import httpx
import pdfplumber
from pydantic import BaseModel

from zoning_agno.config import Settings, get_settings
from zoning_agno.schemas import AtomicFactBundle, AtomicZoningFact, Citation, DistrictRegistryBundle, TemplateSheet
from zoning_agno.services.fact_normalizer import normalize_permission_value, normalize_use_key
from zoning_agno.services.use_crosswalk import canonicalize_use_label, load_use_derivations, use_labels_share_canonical_concept
from zoning_agno.services.use_interpretation import interpret_use_labels

_PDF_TIMEOUT = httpx.Timeout(180.0)
_HEADER_NORMALIZER = re.compile(r"[^A-Z0-9]+")
_DISTRICT_EXPANSIONS: dict[str, list[str]] = {
    "RR": ["RR-1"],
    "RS": ["RS-12", "RS-8", "RS-6"],
}
_USE_LABEL_ALIASES: dict[str, list[str]] = {
    "accessory dwelling unit": ["dwelling - accessory"],
    "single family": ["dwelling - single family detached"],
    "duplex": ["dwelling - duplex"],
    "industrialized housing unit": ["dwelling - industrialized housing unit"],
    "manufactured home": ["dwelling - manufactured home"],
    "mobile home": ["dwelling - mobile home"],
    "multi family": ["dwelling - multiple-family", "multiple-family"],
    "patio home": ["dwelling - patio home"],
    "townhome": ["dwelling - townhome"],
    "church": ["church or place of worship"],
    "college/university": ["university/college"],
    "college university": ["university/college"],
    "day care": ["day-care operation - center-based", "day care operation"],
}
_MATRIX_PAGE_MARKER = "Permitted Uses"


class _TemplateUseCandidate(BaseModel):
    row_key: str
    use_name: str
    use_key: str | None
    normalized_label: str
    canonical_key: str | None = None


def extract_supplemental_use_facts(
    *,
    pdf_urls: list[str],
    template_sheet: TemplateSheet,
    district_registry: DistrictRegistryBundle,
    source_document_id: str,
    source_url: str | None,
    settings: Settings | None = None,
) -> AtomicFactBundle:
    """Recover use-permission facts from a supplemental PDF land use matrix."""
    if not pdf_urls:
        return AtomicFactBundle()
    matrix_tables = _collect_matrix_tables(pdf_urls)
    if not matrix_tables:
        return AtomicFactBundle()
    template_rows = [row for row in template_sheet.rows if str(row.col_c) == "Use Allowance"]
    template_candidates = _build_template_use_candidates(template_rows)
    settings = settings or get_settings()
    unresolved_labels = sorted(
        {
            _clean_cell(row[0])
            for _, _, rows in matrix_tables
            for row in rows[3:]
            if _clean_cell(row[0]) and not _clean_cell(row[0]).endswith("Uses")
            if not _match_template_use_candidates(_clean_cell(row[0]), template_candidates)
        }
    )
    interpreted_matches = interpret_use_labels(
        source_labels=unresolved_labels,
        template_use_names=[candidate.use_name for candidate in template_candidates],
        settings=settings,
    )
    facts: list[AtomicZoningFact] = []
    seen: set[tuple[str, str, str]] = set()
    for pdf_url, page_number, rows in matrix_tables:
        district_codes = [_clean_cell(value) for value in rows[1][1:21]]
        for row in rows[3:]:
            source_label = _clean_cell(row[0])
            if not source_label or source_label.endswith("Uses"):
                continue
            matched_candidates = _match_template_use_candidates(
                source_label,
                template_candidates,
                interpreted_matches=interpreted_matches,
            )
            if not matched_candidates:
                continue
            permissions = row[1:21]
            citation = Citation(
                node_id=None,
                title=f"Land Use Matrix page {page_number}",
                quote=_truncate(" ".join(part for part in [source_label, *(str(value or '') for value in permissions)] if part), 220),
                source_url=pdf_url,
                confidence=0.92,
            )
            for source_district, raw_value in zip(district_codes, permissions, strict=False):
                permission = normalize_permission_value(_clean_cell(raw_value))
                if permission in (None, ""):
                    continue
                for district_code in _expand_source_district_code(source_district, district_registry):
                    for template_candidate in matched_candidates:
                        key = (template_candidate.row_key, district_code, permission)
                        if key in seen:
                            continue
                        seen.add(key)
                        facts.append(
                            AtomicZoningFact(
                                fact_id=f"fact-{uuid4().hex}",
                                source_document_id=source_document_id,
                                node_id=None,
                                section_path=f"Supplemental PDF page {page_number}",
                                fact_type="use_permission",
                                district_code=district_code,
                                use_key=template_candidate.use_key,
                                value_text=permission,
                                value_json={
                                    "template_row_key": template_candidate.row_key,
                                    "use_name": template_candidate.use_name,
                                    "source_use_label": source_label,
                                },
                                citations=[citation],
                                confidence=0.92,
                                requires_human_review=False,
                            )
                        )
    return AtomicFactBundle(facts=facts)


def extract_supplemental_dimensional_facts(
    *,
    pdf_urls: list[str],
    district_registry: DistrictRegistryBundle,
    source_document_id: str,
    source_url: str | None,
) -> AtomicFactBundle:
    """Recover district-aligned facts from structured residential and nonresidential tables."""
    if not pdf_urls:
        return AtomicFactBundle()
    facts: list[AtomicZoningFact] = []
    for pdf_url in pdf_urls:
        with _open_pdf(pdf_url) as pdf:
            for page_number, table_kind, table in _discover_standards_tables(pdf):
                if table_kind == "residential_standards":
                    facts.extend(
                        _extract_residential_standards_facts(
                            table=table,
                            pdf_url=pdf_url,
                            page_number=page_number,
                            district_registry=district_registry,
                            source_document_id=source_document_id,
                        )
                    )
                elif table_kind == "nonresidential_standards":
                    facts.extend(
                        _extract_nonresidential_standards_facts(
                            table=table,
                            pdf_url=pdf_url,
                            page_number=page_number,
                            district_registry=district_registry,
                            source_document_id=source_document_id,
                        )
                    )
    return AtomicFactBundle(facts=_dedupe_facts(facts))


def _collect_matrix_tables(pdf_urls: list[str]) -> list[tuple[str, int, list[list[str | None]]]]:
    tables: list[tuple[str, int, list[list[str | None]]]] = []
    for pdf_url in pdf_urls:
        with _open_pdf(pdf_url) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    if table and table[0] and _MATRIX_PAGE_MARKER in (table[0][0] or ""):
                        tables.append((pdf_url, page.page_number, table))
    return tables


def _extract_residential_standards_facts(
    *,
    table: list[list[str | None]],
    pdf_url: str,
    page_number: int,
    district_registry: DistrictRegistryBundle,
    source_document_id: str,
) -> list[AtomicZoningFact]:
    facts: list[AtomicZoningFact] = []
    for row in _iter_data_rows(table):
        district_code = _coerce_district_code(_clean_cell(row[0]), district_registry)
        if district_code is None:
            continue
        citation = _table_citation(pdf_url, page_number, district_code, row)
        facts.extend(
            _residential_row_to_facts(
                district_code=district_code,
                row=row,
                citation=citation,
                source_document_id=source_document_id,
            )
        )
    return facts


def _extract_nonresidential_standards_facts(
    *,
    table: list[list[str | None]],
    pdf_url: str,
    page_number: int,
    district_registry: DistrictRegistryBundle,
    source_document_id: str,
) -> list[AtomicZoningFact]:
    facts: list[AtomicZoningFact] = []
    for row in _iter_data_rows(table):
        district_code = _coerce_district_code(_clean_cell(row[0]), district_registry)
        if district_code is None:
            continue
        citation = _table_citation(pdf_url, page_number, district_code, row)
        facts.extend(
            _nonresidential_row_to_facts(
                district_code=district_code,
                row=row,
                citation=citation,
                source_document_id=source_document_id,
            )
        )
    return facts


def _discover_standards_tables(pdf) -> list[tuple[int, str, list[list[str | None]]]]:
    matches: list[tuple[int, str, list[list[str | None]]]] = []
    for page in pdf.pages:
        for table in page.extract_tables() or []:
            table_kind = _classify_standards_table(table)
            if table_kind is None:
                continue
            matches.append((page.page_number, table_kind, table))
    return matches


def _classify_standards_table(table: list[list[str | None]]) -> str | None:
    flat_headers = " ".join(_normalize_header(cell) for row in table[:5] for cell in row if cell)
    if "ZONINGDISTRICT" not in flat_headers:
        return None
    if "MAXIMUMDENSITYOFDWELLINGUNITSPERACRE" in flat_headers and "MINIMUMLOTSIZE" in flat_headers:
        return "residential_standards"
    if "MAXIMUMFLOORAREARATIOFAR" in flat_headers and "MINIMUMBUILDINGLINESETBACKS" in flat_headers:
        return "nonresidential_standards"
    return None


def _iter_data_rows(table: list[list[str | None]]) -> list[list[str | None]]:
    rows: list[list[str | None]] = []
    for row in table:
        first = _clean_cell(row[0]) if row else ""
        if not first:
            continue
        normalized = _normalize_header(first)
        if normalized in {
            "ZONINGDISTRICT",
            "PERMITTEDUSES",
            "MAXIMUM",
            "MINIMUM",
            "LOTSIZE",
            "SIZE",
            "DISTRICT",
        }:
            continue
        if len(normalized) > 18 and not re.search(r"\d", normalized):
            continue
        rows.append(row)
    return rows


def _residential_row_to_facts(
    *,
    district_code: str,
    row: list[str | None],
    citation: Citation,
    source_document_id: str,
) -> list[AtomicZoningFact]:
    facts: list[AtomicZoningFact] = []
    mappings = [
        ("LotAreaMin", row[2], "dimensional_standard"),
        ("MinLotWidth", row[3], "dimensional_standard"),
        ("MinLotDepth", row[4], "dimensional_standard"),
        ("MinRearSetback", row[12], "dimensional_standard"),
        ("MinSideSetback", row[13], "dimensional_standard"),
        ("DensityNet", row[1], "district_metadata"),
    ]
    for field_name, raw_value, fact_type in mappings:
        value_numeric = _first_number(raw_value)
        value_text = _clean_cell(raw_value)
        if value_numeric is None and value_text not in {"n/a", "N/A"}:
            continue
        facts.append(
            _make_fact(
                field_name=field_name,
                district_code=district_code,
                fact_type=fact_type,
                value_numeric=value_numeric,
                value_text=value_text,
                citation=citation,
                source_document_id=source_document_id,
            )
        )
    height_text = _clean_cell(row[14])
    height_value = _parse_height_value(height_text)
    if height_value is not None:
        facts.append(
            _make_fact(
                field_name="PrincipalMaxHeightFt",
                district_code=district_code,
                fact_type="dimensional_standard",
                value_numeric=height_value,
                value_text=str(int(height_value) if height_value.is_integer() else height_value),
                citation=citation,
                source_document_id=source_document_id,
            )
        )
    story_value = _parse_story_value(height_text)
    if story_value is not None:
        facts.append(
            _make_fact(
                field_name="PrincipalMaxHeightLvl",
                district_code=district_code,
                fact_type="dimensional_standard",
                value_numeric=story_value,
                value_text=str(int(story_value) if story_value.is_integer() else story_value),
                citation=citation,
                source_document_id=source_document_id,
            )
        )
    return facts


def _nonresidential_row_to_facts(
    *,
    district_code: str,
    row: list[str | None],
    citation: Citation,
    source_document_id: str,
) -> list[AtomicZoningFact]:
    facts: list[AtomicZoningFact] = []
    mappings = [
        ("MinLotWidth", row[1], "dimensional_standard"),
        ("MinLotDepth", row[3], "dimensional_standard"),
        ("MinRearSetback", row[9], "dimensional_standard"),
        ("MinSideSetback", row[10], "dimensional_standard"),
    ]
    for field_name, raw_value, fact_type in mappings:
        value_numeric = _first_number(raw_value)
        if value_numeric is None:
            continue
        facts.append(
            _make_fact(
                field_name=field_name,
                district_code=district_code,
                fact_type=fact_type,
                value_numeric=value_numeric,
                value_text=str(int(value_numeric) if value_numeric.is_integer() else value_numeric),
                citation=citation,
                source_document_id=source_document_id,
            )
        )
    height_text = _clean_cell(row[12])
    height_value = _first_number(height_text)
    if height_value is not None:
        facts.append(
            _make_fact(
                field_name="PrincipalMaxHeightFt",
                district_code=district_code,
                fact_type="dimensional_standard",
                value_numeric=height_value,
                value_text=str(int(height_value) if height_value.is_integer() else height_value),
                citation=citation,
                source_document_id=source_document_id,
            )
        )
    story_value = _parse_story_value(height_text)
    far_value = _parse_far_value(_clean_cell(row[13]))
    if story_value is not None or far_value is not None:
        level_value = story_value if story_value is not None else far_value
        facts.append(
            _make_fact(
                field_name="PrincipalMaxHeightLvl",
                district_code=district_code,
                fact_type="dimensional_standard",
                value_numeric=level_value,
                value_text=str(int(level_value) if level_value.is_integer() else level_value),
                citation=citation,
                source_document_id=source_document_id,
            )
        )
    if far_value is not None:
        facts.append(
            _make_fact(
                field_name="MaximumResidentialFAR",
                district_code=district_code,
                fact_type="district_metadata",
                value_numeric=far_value,
                value_text=str(int(far_value) if far_value.is_integer() else far_value),
                citation=citation,
                source_document_id=source_document_id,
            )
        )
    return facts


def _make_fact(
    *,
    field_name: str,
    district_code: str,
    fact_type: str,
    value_numeric: float | None,
    value_text: str | None,
    citation: Citation,
    source_document_id: str,
) -> AtomicZoningFact:
    return AtomicZoningFact(
        fact_id=f"fact-{uuid4().hex}",
        source_document_id=source_document_id,
        node_id=None,
        section_path=citation.title,
        fact_type=fact_type,
        district_code=district_code,
        field_name=field_name,
        value_numeric=value_numeric,
        value_text=value_text,
        citations=[citation],
        confidence=0.94,
        requires_human_review=False,
    )


def _build_template_use_candidates(template_rows: list[Any]) -> list[_TemplateUseCandidate]:
    candidates: list[_TemplateUseCandidate] = []
    for row in template_rows:
        use_name = str(row.col_b or "")
        crosswalk = canonicalize_use_label(use_name)
        candidates.append(
            _TemplateUseCandidate(
                row_key=row.key,
                use_name=use_name,
                use_key=normalize_use_key(use_name),
                normalized_label=_normalize_use_label(use_name),
                canonical_key=crosswalk.canonical_key if crosswalk else None,
            )
        )
    return candidates


def _match_template_use_candidates(
    source_label: str,
    template_candidates: list[_TemplateUseCandidate],
    *,
    interpreted_matches: dict[str, list[str]] | None = None,
) -> list[_TemplateUseCandidate]:
    source_key = _normalize_use_label(source_label)
    source_crosswalk = canonicalize_use_label(source_label)
    best_candidate = None
    best_score = 0.0
    for candidate in template_candidates:
        if candidate.canonical_key and source_crosswalk and source_crosswalk.canonical_key == candidate.canonical_key:
            score = 0.98
        else:
            score = _use_match_score(source_key, candidate.normalized_label)
        if score > best_score:
            best_score = score
            best_candidate = candidate
    matches: list[_TemplateUseCandidate] = []
    if best_score >= 0.72 and best_candidate is not None:
        matches.append(best_candidate)
    if source_crosswalk:
        derivation_targets = set(load_use_derivations().get(source_crosswalk.canonical_key, []))
        for candidate in template_candidates:
            if candidate.use_name in derivation_targets and candidate not in matches:
                matches.append(candidate)
    if interpreted_matches:
        for candidate in template_candidates:
            if candidate.use_name in interpreted_matches.get(source_label, []) and candidate not in matches:
                matches.append(candidate)
    return matches


def _use_match_score(source_key: str, template_key: str) -> float:
    if source_key == template_key:
        return 1.0
    template_aliases = {_normalize_use_label(value) for value in _USE_LABEL_ALIASES.get(template_key, [])}
    source_aliases = {_normalize_use_label(value) for value in _USE_LABEL_ALIASES.get(source_key, [])}
    if source_key in template_aliases:
        return 0.97
    if template_key in source_aliases:
        return 0.97
    source_tokens = set(source_key.split())
    template_tokens = set(template_key.split())
    if not source_tokens or not template_tokens:
        return 0.0
    if source_tokens <= template_tokens or template_tokens <= source_tokens:
        return 0.95
    overlap = len(source_tokens & template_tokens) / len(source_tokens | template_tokens)
    ratio = SequenceMatcher(None, source_key, template_key).ratio()
    return max(overlap, ratio)


def _normalize_use_label(value: str) -> str:
    normalized = re.sub(r"\([^)]*\)", "", value.lower())
    normalized = normalized.replace("&", " and ").replace("/", " ")
    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"\bdwelling\b", "", normalized)
    normalized = re.sub(r"\boperation\b", "", normalized)
    normalized = re.sub(r"\bunit\b", " unit ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def _expand_source_district_code(source_code: str, district_registry: DistrictRegistryBundle) -> list[str]:
    if not source_code:
        return []
    expanded = _DISTRICT_EXPANSIONS.get(source_code, [source_code])
    allowed = {record.district_code for record in district_registry.districts}
    return [code for code in expanded if code in allowed]


def _coerce_district_code(value: str | None, district_registry: DistrictRegistryBundle) -> str | None:
    if not value:
        return None
    allowed = {record.district_code for record in district_registry.districts}
    return value if value in allowed else None


def _table_citation(pdf_url: str, page_number: int, district_code: str, row: list[str | None]) -> Citation:
    quote = _truncate(" ".join(part for part in [district_code, *(str(cell or "") for cell in row[1:])] if part), 220)
    return Citation(
        node_id=None,
        title=f"Supplemental standards table page {page_number}",
        quote=quote,
        source_url=pdf_url,
        confidence=0.94,
    )


def _parse_far_value(value: str | None) -> float | None:
    if not value or value.lower() == "none":
        return None
    match = re.search(r"(\d+(?:/\d+)?(?:\.\d+)?)\s*:\s*1", value)
    if not match:
        return _first_number(value)
    raw = match.group(1)
    if "/" in raw and raw.count("/") == 1 and "." not in raw:
        num, den = raw.split("/", 1)
        return float(num) / float(den)
    return float(raw)


def _parse_story_value(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*stor", value, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def _parse_height_value(value: str | None) -> float | None:
    if not value:
        return None
    if "over 45 ft" in value.lower():
        return 45.0
    return _first_number(value)


def _first_number(value: str | None) -> float | None:
    if not value or value.lower() in {"none", "n/a"}:
        return None
    match = re.search(r"(-?\d+(?:\.\d+)?)", value.replace(",", ""))
    return float(match.group(1)) if match else None


def _clean_cell(value: Any) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())


def _normalize_header(value: str | None) -> str:
    return _HEADER_NORMALIZER.sub("", str(value or "").upper())


def _truncate(value: str, limit: int) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _dedupe_facts(facts: Iterable[AtomicZoningFact]) -> list[AtomicZoningFact]:
    deduped: list[AtomicZoningFact] = []
    seen: set[tuple[str | None, str | None, str | None, str | None, str | None]] = set()
    for fact in facts:
        key = (fact.fact_type, fact.district_code, fact.field_name, fact.use_key, fact.value_text)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(fact)
    return deduped


def _open_pdf(source: str):
    return pdfplumber.open(BytesIO(_download_pdf_bytes(source)))


@lru_cache(maxsize=8)
def _download_pdf_bytes(source: str) -> bytes:
    with httpx.Client(timeout=_PDF_TIMEOUT, follow_redirects=True) as client:
        response = client.get(source)
        response.raise_for_status()
        return response.content
