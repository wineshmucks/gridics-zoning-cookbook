from __future__ import annotations

import re
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from zoning_agno.db.models import LegalChunkORM, LegalSectionORM, SourceDocumentORM
from zoning_agno.schemas import Citation, DistrictRegistryBundle, DistrictRegistryRecord, TemplateSheet

_DISTRICT_CODE_RE = re.compile(r"\b([A-Z]{2,4}(?:-\d{1,2})?)\b")
_DISTRICT_CONTEXT_RE = re.compile(r"\b(?:districts?|zones?|overlay|overlays|zoning)\b", re.IGNORECASE)
_KNOWN_CODES = {
    "AO",
    "CB",
    "CBD",
    "CU",
    "GC",
    "GR",
    "HC",
    "HI",
    "LI",
    "MH",
    "NO",
    "PD",
    "RM-2",
    "RM-3",
    "RR-1",
    "RS-6",
    "RS-8",
    "RS-12",
}


def normalize_district_code(value: str | None) -> str | None:
    """Normalize district labels into canonical Gridics-style codes."""
    if not value:
        return None
    normalized = (
        value.upper()
        .replace("–", "-")
        .replace("—", "-")
        .replace(" ", "")
        .replace(".", "")
        .strip()
    )
    return normalized or None


def extract_district_codes_from_titles(values: Iterable[str]) -> list[str]:
    """Extract likely district codes from titles/headings with zoning context."""
    matches: list[str] = []
    patterns = [
        re.compile(r"\b([A-Z]{2,4}(?:-\d{1,2})?)\b\s*[-:]\s*[^.]+?(?:district|zone|overlay)\b", re.IGNORECASE),
        re.compile(r"\b([A-Z]{2,4}(?:-\d{1,2})?)\b\s+[^.]+?(?:district|zone|overlay)\b", re.IGNORECASE),
        re.compile(r"(?:district|zone|overlay)\s+([A-Z]{2,4}(?:-\d{1,2})?)\b", re.IGNORECASE),
    ]
    for raw_value in values:
        value = str(raw_value or "")
        for pattern in patterns:
            for match in pattern.findall(value):
                normalized = normalize_district_code(match)
                if _is_likely_district_code(normalized):
                    matches.append(normalized)
    return _dedupe_codes(matches)


def extract_district_codes_from_tables(values: Iterable[str]) -> list[str]:
    """Extract likely district codes from table or matrix-like text."""
    return _dedupe_codes(_extract_codes(values, require_context=False))


def extract_district_codes_from_text(values: Iterable[str]) -> list[str]:
    """Extract district codes from prose only when zoning context is present nearby."""
    return _dedupe_codes(_extract_codes(values, require_context=True))


def build_district_registry(session: Session, source_document_id: int) -> DistrictRegistryBundle:
    """Build an evidence-backed district registry for district-pivoted Gridics exports."""
    source_document = session.get(SourceDocumentORM, source_document_id)
    if source_document is None:
        raise ValueError(f"Source document not found: {source_document_id}")

    records: dict[str, dict[str, object]] = {}
    section_rows = session.scalars(
        select(LegalSectionORM)
        .where(LegalSectionORM.source_document_id == source_document_id)
        .order_by(LegalSectionORM.id)
    ).all()
    chunk_rows = session.scalars(
        select(LegalChunkORM)
        .where(LegalChunkORM.source_document_id == source_document_id)
        .order_by(LegalChunkORM.id)
    ).all()

    for section in section_rows:
        evidence_texts = [section.title or "", section.subtitle or "", section.section_path or ""]
        for code in extract_district_codes_from_titles(evidence_texts):
            _add_evidence(
                records,
                code=code,
                node_id=section.node_id,
                title=section.title or section.subtitle or section.section_path,
                quote=_best_quote(evidence_texts),
                source_url=source_document.source_url,
                district_name=_extract_district_name(section.title, code) or _extract_district_name(section.subtitle, code),
                confidence=0.95,
                position=section.id or 0,
            )
        for code in extract_district_codes_from_text([section.body_text]):
            _add_evidence(
                records,
                code=code,
                node_id=section.node_id,
                title=section.title or section.subtitle or section.section_path,
                quote=_truncate(section.body_text, 180),
                source_url=source_document.source_url,
                district_name=None,
                confidence=0.7,
                position=section.id or 0,
            )

    for chunk in chunk_rows:
        if chunk.chunk_type not in {"table_text", "use_matrix", "dimensional_rule", "parking_rule"}:
            continue
        for code in extract_district_codes_from_tables([chunk.title or "", chunk.subtitle or "", chunk.chunk_text]):
            _add_evidence(
                records,
                code=code,
                node_id=chunk.node_id,
                title=chunk.title or chunk.subtitle or chunk.section_path,
                quote=_truncate(chunk.chunk_text, 180),
                source_url=source_document.source_url,
                district_name=_extract_district_name(chunk.title, code) or _extract_district_name(chunk.subtitle, code),
                confidence=0.85 if chunk.chunk_type in {"use_matrix", "table_text"} else 0.75,
                position=chunk.id or 0,
            )

    ordered = sorted(
        (
            DistrictRegistryRecord(
                district_code=code,
                district_name=entry.get("district_name"),
                district_family="overlay" if code == "PD" else "zone",
                source_node_id=entry.get("source_node_id"),
                source_title=entry.get("source_title"),
                citations=entry.get("citations", []),
                confidence=float(entry.get("confidence") or 0.0),
            )
            for code, entry in records.items()
        ),
        key=lambda item: (
            int(records[item.district_code].get("position") or 0),
            item.district_code,
        ),
    )
    return DistrictRegistryBundle(districts=ordered)


def build_district_registry_from_template(template_sheet: TemplateSheet) -> DistrictRegistryBundle:
    """Build canonical export districts directly from the Gridics template header order."""
    return DistrictRegistryBundle(
        districts=[
            DistrictRegistryRecord(
                district_code=header,
                district_name=None,
                district_family="zone",
                source_title=f"{template_sheet.sheet_name} header",
                citations=[],
                confidence=1.0,
            )
            for header in template_sheet.header.district_headers
        ]
    )


def reconcile_extracted_districts_with_template(
    template_districts: DistrictRegistryBundle,
    extracted_districts: DistrictRegistryBundle,
) -> DistrictRegistryBundle:
    """Preserve template column order while layering extracted evidence onto matching headers."""
    extracted_by_normalized = {
        _normalize_for_lookup(record.district_code): record
        for record in extracted_districts.districts
    }
    reconciled: list[DistrictRegistryRecord] = []
    for template_record in template_districts.districts:
        matched = extracted_by_normalized.get(_normalize_for_lookup(template_record.district_code))
        if matched is None:
            reconciled.append(template_record)
            continue
        reconciled.append(
            DistrictRegistryRecord(
                district_code=template_record.district_code,
                district_name=matched.district_name or template_record.district_name,
                district_family=matched.district_family or template_record.district_family,
                source_node_id=matched.source_node_id,
                source_title=matched.source_title or template_record.source_title,
                citations=matched.citations,
                confidence=matched.confidence,
            )
        )
    return DistrictRegistryBundle(districts=reconciled)


def _extract_codes(values: Iterable[str], *, require_context: bool) -> list[str]:
    matches: list[str] = []
    for raw_value in values:
        value = str(raw_value or "")
        if not value:
            continue
        if require_context and not _DISTRICT_CONTEXT_RE.search(value):
            continue
        for match in _DISTRICT_CODE_RE.findall(value.upper()):
            normalized = normalize_district_code(match)
            if _is_likely_district_code(normalized):
                matches.append(normalized)
    return matches


def _is_likely_district_code(value: str | None) -> bool:
    if not value:
        return False
    if value in _KNOWN_CODES:
        return True
    if re.fullmatch(r"R[MRS]{1,2}-\d{1,2}", value):
        return True
    return False


def _dedupe_codes(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _extract_district_name(text: str | None, code: str) -> str | None:
    if not text:
        return None
    normalized = " ".join(text.split())
    patterns = [
        re.compile(rf"\b{re.escape(code)}\b\s*[-:]\s*(.+)$", re.IGNORECASE),
        re.compile(rf"\b{re.escape(code)}\b\s+(.+?)(?:\s+district)?$", re.IGNORECASE),
        re.compile(rf"(.+?)\s+\(\s*{re.escape(code)}\s*\)$", re.IGNORECASE),
    ]
    for pattern in patterns:
        match = pattern.search(normalized)
        if match:
            candidate = match.group(1).strip(" -:")
            if candidate and candidate.upper() != code:
                return candidate
    return None


def _add_evidence(
    records: dict[str, dict[str, object]],
    *,
    code: str,
    node_id: str | None,
    title: str | None,
    quote: str,
    source_url: str | None,
    district_name: str | None,
    confidence: float,
    position: int,
) -> None:
    entry = records.setdefault(
        code,
        {
            "district_name": None,
            "source_node_id": node_id,
            "source_title": title,
            "citations": [],
            "confidence": confidence,
            "position": position,
        },
    )
    citations = entry["citations"]
    assert isinstance(citations, list)
    citations.append(
        Citation(
            node_id=node_id,
            title=title,
            quote=quote,
            source_url=source_url,
            confidence=confidence,
        )
    )
    if district_name and not entry.get("district_name"):
        entry["district_name"] = district_name
    if confidence >= float(entry.get("confidence") or 0.0):
        entry["source_node_id"] = node_id
        entry["source_title"] = title
        entry["confidence"] = confidence
    entry["position"] = min(int(entry.get("position") or position), position)


def _best_quote(values: Iterable[str]) -> str:
    for value in values:
        if value and str(value).strip():
            return _truncate(str(value), 180)
    return "District evidence"


def _truncate(value: str, limit: int) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _normalize_for_lookup(value: str | None) -> str:
    return normalize_district_code((value or "").replace("/", "").replace("_", "").replace(" ", "")) or ""
