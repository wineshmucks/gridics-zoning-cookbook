from __future__ import annotations

import re
from typing import Iterable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from zoning_agno.db.models import LegalChunkORM, SourceDocumentORM
from zoning_agno.schemas import AtomicFactBundle, AtomicZoningFact, Citation, DistrictRegistryBundle, TemplateSheet
from zoning_agno.services.fact_normalizer import (
    flag_ambiguous_fact,
    normalize_field_name,
    normalize_numeric_unit,
    normalize_permission_value,
    normalize_use_key,
)
from zoning_agno.services.supplemental_pdf_facts import (
    extract_supplemental_dimensional_facts,
    extract_supplemental_use_facts,
)
from zoning_agno.services.supplemental_sources import get_supplemental_source_urls

_FIELD_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bminimum lot area\b", re.IGNORECASE), "minimum lot area"),
    (re.compile(r"\bminimum lot width\b", re.IGNORECASE), "minimum lot width"),
    (re.compile(r"\blot depth\b", re.IGNORECASE), "lot depth"),
    (re.compile(r"\bfront setback\b", re.IGNORECASE), "front setback"),
    (re.compile(r"\brear setback\b", re.IGNORECASE), "rear setback"),
    (re.compile(r"\bside setback\b", re.IGNORECASE), "side setback"),
    (re.compile(r"\bmaximum height\b|\bbuilding height\b|\bheight\b", re.IGNORECASE), "maximum height"),
]
_ZONING_HINT = re.compile(
    r"\b(zoning|district|overlay|land development code|land use matrix|site layout|setback|lot area|lot width|lot depth|density|dwelling|building requirements|commercial|residential|industrial)\b",
    re.IGNORECASE,
)
_DISTRICT_CODE_PATTERN = re.compile(r"\b([A-Z]{1,4}(?:-\d{1,2})?)\b")
_DENSITY_DISTRICT_PATTERN = re.compile(
    r"\b([A-Z]{1,4}(?:-\d{1,2})?)\b[^\n()]{0,120}?\(\s*maximum\s+(\d+(?:\.\d+)?)\s+units?\s+per\s+(?:gross\s+)?acre",
    re.IGNORECASE,
)
_BOOLEAN_USE_CAPACITY_HINTS: dict[str, tuple[re.Pattern[str], bool]] = {
    "DensityUL": (re.compile(r"\bmaximum\s+\d+(?:\.\d+)?\s+units?\s+per\s+(?:gross\s+)?acre\b", re.IGNORECASE), True),
    "Minimum1DwellingUnit": (re.compile(r"\bmaximum\s+of\s+one\s*\(\s*1\s*\)\s+dwelling unit per lot\b", re.IGNORECASE), True),
}
_DENSITY_VALUE_PATTERN = re.compile(
    r"\bmaximum(?:\s+of)?\s+(?:[a-z-]+\s*\(\s*)?(\d+(?:\.\d+)?)\s*(?:\))?\s+dwelling units?\s+per\s+(?:gross\s+)?acre\b",
    re.IGNORECASE,
)


def extract_dimensional_facts(
    session: Session,
    source_document_id: int,
    district_registry: DistrictRegistryBundle,
) -> AtomicFactBundle:
    """Extract atomic dimensional facts from normalized dimensional-rule chunks."""
    source_document = session.get(SourceDocumentORM, source_document_id)
    if source_document is None:
        raise ValueError(f"Source document not found: {source_document_id}")
    chunks = session.scalars(
        select(LegalChunkORM)
        .where(
            LegalChunkORM.source_document_id == source_document_id,
            LegalChunkORM.chunk_type.in_(["dimensional_rule", "table_text"]),
        )
        .order_by(LegalChunkORM.id)
    ).all()
    chunks = [chunk for chunk in chunks if _is_likely_zoning_chunk(chunk)]
    facts = _extract_dimensional_facts_from_chunks(
            chunks=chunks,
            district_registry=district_registry,
            source_document_id=str(source_document_id),
            source_url=source_document.source_url,
        )
    supplemental_pdf_urls = get_supplemental_source_urls(session, source_document_id)
    if supplemental_pdf_urls:
        facts.extend(
            extract_supplemental_dimensional_facts(
                pdf_urls=supplemental_pdf_urls,
                district_registry=district_registry,
                source_document_id=str(source_document_id),
                source_url=source_document.source_url,
            ).facts
        )
    return AtomicFactBundle(facts=facts)


def extract_use_permission_facts(
    session: Session,
    source_document_id: int,
    district_registry: DistrictRegistryBundle,
    *,
    template_sheet: TemplateSheet | None = None,
) -> AtomicFactBundle:
    """Extract atomic use-permission facts using the template use catalog as the target row set."""
    source_document = session.get(SourceDocumentORM, source_document_id)
    if source_document is None:
        raise ValueError(f"Source document not found: {source_document_id}")
    if template_sheet is None:
        return AtomicFactBundle()
    chunks = session.scalars(
        select(LegalChunkORM)
        .where(
            LegalChunkORM.source_document_id == source_document_id,
            LegalChunkORM.chunk_type.in_(["use_matrix", "section_text"]),
        )
        .order_by(LegalChunkORM.id)
    ).all()
    chunks = [chunk for chunk in chunks if _is_likely_zoning_chunk(chunk)]
    facts: list[AtomicZoningFact] = []
    for row in template_sheet.rows:
        if str(row.col_c) != "Use Allowance":
            continue
        use_name = str(row.col_b or "").strip()
        if not use_name:
            continue
        variants = _use_name_variants(use_name)
        for chunk in chunks:
            lowered = (chunk.chunk_text or "").lower()
            if not any(variant in lowered for variant in variants):
                continue
            permission = _infer_permission_from_text(chunk.chunk_text)
            if permission is None:
                continue
            districts = _districts_from_chunk_context(chunk, district_registry)
            if not districts:
                districts = [None]
            for district_code in districts:
                facts.append(
                    AtomicZoningFact(
                        fact_id=f"fact-{uuid4().hex}",
                        source_document_id=str(source_document_id),
                        node_id=chunk.node_id,
                        section_path=chunk.section_path,
                        fact_type="use_permission",
                        district_code=district_code,
                        use_key=normalize_use_key(use_name),
                        value_text=permission,
                        value_json={"template_row_key": row.key, "use_name": use_name, "use_value_type": row.col_c},
                        citations=[
                            Citation(
                                section_id=chunk.legal_section_id,
                                node_id=chunk.node_id,
                                title=chunk.title or chunk.subtitle or chunk.section_path,
                                quote=_truncate(chunk.chunk_text, 220),
                                source_url=source_document.source_url,
                                confidence=0.75,
                            )
                        ],
                        confidence=0.75 if district_code else 0.4,
                        requires_human_review=flag_ambiguous_fact(
                            has_district_code=bool(district_code),
                            has_field_name=True,
                            has_value=True,
                        ),
                    )
                )
    supplemental_pdf_urls = get_supplemental_source_urls(session, source_document_id)
    if supplemental_pdf_urls:
        facts.extend(
            extract_supplemental_use_facts(
                pdf_urls=supplemental_pdf_urls,
                template_sheet=template_sheet,
                district_registry=district_registry,
                source_document_id=str(source_document_id),
                source_url=source_document.source_url,
            ).facts
        )
    return AtomicFactBundle(facts=_dedupe_atomic_facts(facts))


def extract_parking_facts(*args, **kwargs) -> AtomicFactBundle:
    """Placeholder for the next target; returns an empty bundle for now."""
    return AtomicFactBundle()


def extract_overlay_modifier_facts(*args, **kwargs) -> AtomicFactBundle:
    """Placeholder for the next target; returns an empty bundle for now."""
    return AtomicFactBundle()


def extract_district_metadata_facts(*args, **kwargs) -> AtomicFactBundle:
    """Placeholder for the next target; returns an empty bundle for now."""
    return AtomicFactBundle()


def _extract_dimensional_facts_from_chunks(
    *,
    chunks: Iterable[LegalChunkORM],
    district_registry: DistrictRegistryBundle,
    source_document_id: str,
    source_url: str | None,
) -> list[AtomicZoningFact]:
    facts: list[AtomicZoningFact] = []
    for chunk in chunks:
        facts.extend(
            _extract_density_metadata_facts(
                chunk=chunk,
                district_registry=district_registry,
                source_document_id=source_document_id,
                source_url=source_url,
            )
        )
        districts = _districts_from_chunk_context(chunk, district_registry)
        field_name = _detect_field_name(chunk.chunk_text, chunk.title, chunk.subtitle)
        value_text = _extract_value_text(chunk.chunk_text)
        value_numeric, unit = normalize_numeric_unit(value_text or chunk.chunk_text)
        if not districts:
            districts = [None]
        for district_code in districts:
            citations = [
                Citation(
                    section_id=chunk.legal_section_id,
                    node_id=chunk.node_id,
                    title=chunk.title or chunk.subtitle or chunk.section_path,
                    quote=_truncate(chunk.chunk_text, 220),
                    source_url=source_url,
                    confidence=0.75,
                )
            ]
            facts.append(
                AtomicZoningFact(
                    fact_id=f"fact-{uuid4().hex}",
                    source_document_id=source_document_id,
                    node_id=chunk.node_id,
                    section_path=chunk.section_path,
                    fact_type="dimensional_standard",
                    district_code=district_code,
                    field_name=field_name,
                    value_text=value_text,
                    value_numeric=value_numeric,
                    unit=unit,
                    citations=citations,
                    confidence=0.75 if district_code and field_name and value_text else 0.45,
                    requires_human_review=flag_ambiguous_fact(
                        has_district_code=bool(district_code),
                        has_field_name=bool(field_name),
                        has_value=bool(value_text),
                    ),
                )
            )
    return facts


def _mentions_district(text: str | None, title: str | None, district_code: str) -> bool:
    haystack = " ".join(part for part in [title or "", text or ""] if part)
    return bool(re.search(rf"\b{re.escape(district_code)}\b", haystack, re.IGNORECASE))


def _districts_from_heading(value: str | None, district_registry: DistrictRegistryBundle) -> list[str]:
    if not value:
        return []
    matches: list[str] = []
    for record in district_registry.districts:
        if _mentions_district(value, None, record.district_code):
            matches.append(record.district_code)
    return matches


def _districts_from_chunk_context(chunk: LegalChunkORM, district_registry: DistrictRegistryBundle) -> list[str]:
    matches = [
        record.district_code
        for record in district_registry.districts
        if _mentions_district(chunk.chunk_text, chunk.title, record.district_code)
        or _mentions_district(chunk.subtitle, chunk.title, record.district_code)
    ]
    if matches:
        return list(dict.fromkeys(matches))
    for value in [chunk.subtitle, chunk.title, chunk.section_path]:
        heading_matches = _districts_from_heading(value, district_registry)
        if heading_matches:
            return heading_matches
    expanded = _expand_district_group_aliases(chunk.chunk_text or "", district_registry)
    if expanded:
        return expanded
    return []


def _expand_district_group_aliases(text: str, district_registry: DistrictRegistryBundle) -> list[str]:
    lowered = text.lower()
    if "all districts" in lowered:
        return [record.district_code for record in district_registry.districts]
    if "residential districts" in lowered or "residential zoning districts" in lowered:
        return [record.district_code for record in district_registry.districts if _is_residential_district(record.district_code)]
    if "nonresidential districts" in lowered or "nonresidential zoning districts" in lowered:
        return [record.district_code for record in district_registry.districts if not _is_residential_district(record.district_code)]
    groups: list[str] = []
    for match in _DISTRICT_CODE_PATTERN.findall(text.upper()):
        if match in {"AO", "CB", "CU", "GC", "GR", "HC", "HI", "LI", "MH", "NO", "NR", "O", "MF", "MD", "MU", "MX", "PH", "TH", "PD", "CBD"}:
            groups.append(match)
        elif match in {"RR", "RS", "RM"}:
            groups.extend(record.district_code for record in district_registry.districts if record.district_code.startswith(match + "-"))
    return list(dict.fromkeys(code for code in groups if any(record.district_code == code for record in district_registry.districts)))


def _detect_field_name(*values: str | None) -> str | None:
    haystack = " ".join(str(value or "") for value in values)
    for pattern, label in _FIELD_PATTERNS:
        if pattern.search(haystack):
            return normalize_field_name(label)
    return None


def _extract_value_text(text: str | None) -> str | None:
    if not text:
        return None
    matches = re.findall(
        r"(?:is|shall be|must be|=)?\s*(-?\d[\d,]*(?:\.\d+)?)\s*(square feet|sq\.?\s*ft|sq ft|feet|foot|ft|stories|story|%)?",
        text,
        re.IGNORECASE,
    )
    if not matches:
        return None
    number, unit = matches[-1]
    return f"{number} {unit}".strip()


def _truncate(value: str, limit: int) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _use_name_variants(use_name: str) -> set[str]:
    lowered = use_name.lower()
    variants = {lowered}
    variants.add(lowered.replace("&", "and"))
    if lowered.endswith(" unit"):
        variants.add(lowered + "s")
    if lowered.endswith(" units"):
        variants.add(lowered[:-1])
    if "dwelling unit" in lowered:
        variants.add(lowered.replace("dwelling unit", "dwelling units"))
    if "home occupation" in lowered:
        variants.add(lowered.replace("home occupation", "home occupations"))
    return variants


def _infer_permission_from_text(text: str | None) -> str | None:
    lowered = (text or "").lower()
    code_match = re.search(r"\b(PC-\d+|SE-\d+|NP|PC|SE|P)\b", (text or "").upper())
    if code_match:
        return normalize_permission_value(code_match.group(1))
    if "not permitted" in lowered or "prohibited" in lowered:
        return normalize_permission_value("NP")
    if "special exception" in lowered:
        return normalize_permission_value("SE")
    if "conditional" in lowered or "conditionally" in lowered:
        return normalize_permission_value("PC")
    if "permitted" in lowered or "authorized" in lowered or "allowed" in lowered:
        return normalize_permission_value("P")
    return None


def _is_likely_zoning_chunk(chunk: LegalChunkORM) -> bool:
    node_id = chunk.node_id or ""
    if "CH2ZORE" in node_id:
        return True
    haystack = " ".join(part for part in [chunk.title or "", chunk.subtitle or "", chunk.section_path or "", chunk.chunk_text or ""] if part)
    return bool(_ZONING_HINT.search(haystack))


def _is_residential_district(district_code: str) -> bool:
    return district_code == "AO" or district_code.startswith(("RR-", "RS-", "RM-")) or district_code in {"MH", "MF", "MD", "TH", "PH"}


def _extract_density_metadata_facts(
    *,
    chunk: LegalChunkORM,
    district_registry: DistrictRegistryBundle,
    source_document_id: str,
    source_url: str | None,
) -> list[AtomicZoningFact]:
    facts: list[AtomicZoningFact] = []
    text = chunk.chunk_text or ""
    seen: set[tuple[str, str]] = set()
    context_districts = _districts_from_chunk_context(chunk, district_registry)
    citations = [
        Citation(
            section_id=chunk.legal_section_id,
            node_id=chunk.node_id,
            title=chunk.title or chunk.subtitle or chunk.section_path,
            quote=_truncate(text, 220),
            source_url=source_url,
            confidence=0.8,
        )
    ]
    for code, raw_value in _DENSITY_DISTRICT_PATTERN.findall(text):
        normalized_code = code.upper()
        district_code = next(
            (record.district_code for record in district_registry.districts if record.district_code.upper() == normalized_code),
            None,
        )
        if district_code is None:
            continue
        value_numeric = float(raw_value)
        for field_name in ["DensityNet", "MaximumResidentialFAR"]:
            if (district_code, field_name) in seen:
                continue
            seen.add((district_code, field_name))
            facts.append(
                AtomicZoningFact(
                    fact_id=f"fact-{uuid4().hex}",
                    source_document_id=source_document_id,
                    node_id=chunk.node_id,
                    section_path=chunk.section_path,
                    fact_type="district_metadata",
                    district_code=district_code,
                    field_name=field_name,
                    value_numeric=value_numeric,
                    value_text=str(int(value_numeric) if value_numeric.is_integer() else value_numeric),
                    citations=citations,
                    confidence=0.8,
                        requires_human_review=False,
                    )
                )
    density_match = _DENSITY_VALUE_PATTERN.search(text)
    if density_match:
        value_numeric = float(density_match.group(1))
        for district_code in context_districts:
            for field_name in ["DensityNet", "MaximumResidentialFAR", "DensityUL"]:
                if (district_code, field_name) in seen:
                    continue
                seen.add((district_code, field_name))
                facts.append(
                    AtomicZoningFact(
                        fact_id=f"fact-{uuid4().hex}",
                        source_document_id=source_document_id,
                        node_id=chunk.node_id,
                        section_path=chunk.section_path,
                        fact_type="district_metadata",
                        district_code=district_code,
                        field_name=field_name,
                        value_numeric=value_numeric if field_name != "DensityUL" else None,
                        value_text=(str(int(value_numeric) if value_numeric.is_integer() else value_numeric) if field_name != "DensityUL" else "true"),
                        value_json={"boolean_value": True} if field_name == "DensityUL" else None,
                        citations=citations,
                        confidence=0.78,
                        requires_human_review=False,
                    )
                )
    for district_code in context_districts:
        for field_name, (pattern, value) in _BOOLEAN_USE_CAPACITY_HINTS.items():
            if not pattern.search(text) or (district_code, field_name) in seen:
                continue
            seen.add((district_code, field_name))
            facts.append(
                AtomicZoningFact(
                    fact_id=f"fact-{uuid4().hex}",
                    source_document_id=source_document_id,
                    node_id=chunk.node_id,
                    section_path=chunk.section_path,
                    fact_type="district_metadata",
                    district_code=district_code,
                    field_name=field_name,
                    value_text=str(value).lower(),
                    value_json={"boolean_value": value},
                    citations=citations,
                    confidence=0.75,
                    requires_human_review=False,
                )
            )
    return facts


def _dedupe_atomic_facts(facts: list[AtomicZoningFact]) -> list[AtomicZoningFact]:
    deduped: list[AtomicZoningFact] = []
    seen: set[tuple[str, str | None, str | None, str | None, str | None, str | None]] = set()
    for fact in facts:
        key = (
            fact.fact_type,
            fact.district_code,
            fact.field_name,
            fact.use_key,
            fact.value_text,
            str((fact.value_json or {}).get("template_row_key")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(fact)
    return deduped
