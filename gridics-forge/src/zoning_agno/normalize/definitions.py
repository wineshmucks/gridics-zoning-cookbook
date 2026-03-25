from __future__ import annotations

import re

from zoning_agno.schemas import LegalSection

_DEFINITION_LINE_PATTERN = re.compile(
    r'^\s*(?:"(?P<quoted>[^"]+)"|(?P<term>[A-Z][A-Za-z0-9\s/\-&,()]+))\s+(?:means|shall mean|is defined as)\s+(?P<definition>.+)$',
    re.IGNORECASE,
)


def _looks_like_definition_section(section: LegalSection) -> bool:
    haystack = " ".join(filter(None, [section.title, section.subtitle, section.section_path]))
    return "definition" in haystack.lower()


def extract_definitions(sections: list[LegalSection]) -> list[dict[str, object]]:
    """Extract definition records from sections that appear to contain defined terms."""
    definitions: list[dict[str, object]] = []
    for section in sections:
        if not _looks_like_definition_section(section):
            continue
        for raw_line in section.body_text.splitlines():
            line = " ".join(raw_line.split())
            if not line:
                continue
            match = _DEFINITION_LINE_PATTERN.match(line)
            if not match:
                continue
            term = (match.group("quoted") or match.group("term") or "").strip(" -:;")
            definition = match.group("definition").strip()
            if not term or not definition:
                continue
            definitions.append(
                {
                    "source_document_id": section.source_document_id,
                    "term": term,
                    "definition_text": definition,
                    "section_id": section.id,
                    "node_id": section.node_id,
                }
            )
    return definitions
