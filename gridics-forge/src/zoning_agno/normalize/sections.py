from __future__ import annotations

import re

from zoning_agno.schemas import LegalSection, MuniNode

_TITLE_LEVEL_PATTERNS: list[tuple[str, re.Pattern[str], int]] = [
    ("chapter", re.compile(r"^chapter\s+\d+[a-z]?$", re.IGNORECASE), 1),
    ("article", re.compile(r"^article\s+[ivxlc0-9]+$", re.IGNORECASE), 2),
    ("division", re.compile(r"^division\s+\d+$", re.IGNORECASE), 3),
    ("section", re.compile(r"^(sec\.|section)\s+[\d\-\.]+$", re.IGNORECASE), 4),
]


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = "\n".join(line.rstrip() for line in str(value).replace("\r\n", "\n").splitlines())
    normalized = normalized.strip()
    return normalized or None


def _title_level(title: str | None) -> tuple[str, int]:
    normalized = _clean_text(title) or ""
    for section_type, pattern, level in _TITLE_LEVEL_PATTERNS:
        if pattern.match(normalized):
            return section_type, level
    if normalized:
        return "section", 4
    return "section", 5


def _path_label(node: MuniNode) -> str:
    parts = [part for part in [_clean_text(node.title), _clean_text(node.subtitle)] if part]
    if parts:
        return " - ".join(parts)
    return node.node_id or f"row-{node.row_number}"


def normalize_sections(nodes: list[MuniNode], source_document_id: int | None = None) -> list[LegalSection]:
    """Convert raw Municode rows into legal sections with inferred hierarchy."""
    sections: list[LegalSection] = []
    hierarchy_stack: list[tuple[int, str]] = []
    parent_id_stack: list[tuple[int, int]] = []

    for ordinal, node in enumerate(nodes, start=1):
        title = _clean_text(node.title)
        subtitle = _clean_text(node.subtitle)
        body_text = _clean_text(node.content)
        if not any([title, subtitle, body_text]):
            continue

        section_type, level = _title_level(title)
        while hierarchy_stack and hierarchy_stack[-1][0] >= level:
            hierarchy_stack.pop()
        while parent_id_stack and parent_id_stack[-1][0] >= level:
            parent_id_stack.pop()

        label = _path_label(node)
        path_parts = [part for _, part in hierarchy_stack] + [label]
        parent_section_id = parent_id_stack[-1][1] if parent_id_stack else None
        section = LegalSection(
            id=ordinal,
            source_document_id=source_document_id,
            node_id=node.node_id,
            section_path=" > ".join(path_parts),
            title=title,
            subtitle=subtitle,
            body_text=body_text or "",
            section_type=section_type,
            parent_section_id=parent_section_id,
        )
        sections.append(section)

        hierarchy_stack.append((level, label))
        parent_id_stack.append((level, ordinal))

    return sections
