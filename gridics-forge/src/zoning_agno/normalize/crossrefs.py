from __future__ import annotations

import re

from zoning_agno.schemas import LegalSection

_CROSSREF_PATTERNS = [
    re.compile(r"\bSec\.\s*\d+(?:-\d+)?(?:\.\d+)*\b", re.IGNORECASE),
    re.compile(r"\bSection\s+\d+(?:\.\d+)+(?:\.\d+)*\b", re.IGNORECASE),
    re.compile(r"\bChapter\s+\d+[A-Za-z]?\b", re.IGNORECASE),
    re.compile(r"\bArticle\s+[IVXLC]+\b", re.IGNORECASE),
    re.compile(r"\bDivision\s+\d+\b", re.IGNORECASE),
]


def extract_cross_references(text: str) -> list[str]:
    """Extract normalized legal cross-reference strings from raw section text."""
    seen: set[str] = set()
    matches: list[str] = []
    for pattern in _CROSSREF_PATTERNS:
        for match in pattern.findall(text or ""):
            cleaned = " ".join(match.split())
            key = cleaned.lower()
            if key not in seen:
                seen.add(key)
                matches.append(cleaned)
    return matches


def build_cross_reference_rows(sections: list[LegalSection]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for section in sections:
        for ref in extract_cross_references(section.body_text):
            rows.append(
                {
                    "source_document_id": section.source_document_id,
                    "from_section_id": section.id,
                    "to_section_ref": ref,
                    "to_section_id": None,
                    "ref_text": ref,
                }
            )
    return rows
