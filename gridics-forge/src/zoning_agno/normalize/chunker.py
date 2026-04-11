from __future__ import annotations

import math
import re

from zoning_agno.schemas import LegalChunk, LegalSection

_TABLE_HINT = re.compile(r"\btable\b|\|", re.IGNORECASE)
_PARKING_HINT = re.compile(r"\bparking\b", re.IGNORECASE)
_DIMENSION_HINT = re.compile(r"\b(minimum|max(?:imum)?|setback|height|width|lot area|floor area ratio|far)\b", re.IGNORECASE)
_USE_HINT = re.compile(r"\b(permitted|conditional|prohibited|use matrix|accessory use)\b", re.IGNORECASE)
_FOOTNOTE_HINT = re.compile(r"^\s*\(\d+\)|^\s*note:", re.IGNORECASE)


def _paragraphs(text: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"\n\s*\n", text or "") if part.strip()]
    return parts or ([text.strip()] if text and text.strip() else [])


def _chunk_type(section: LegalSection, text: str) -> str:
    haystack = " ".join(filter(None, [section.title, section.subtitle, text]))
    if "definition" in haystack.lower():
        return "definition"
    if _PARKING_HINT.search(haystack):
        return "parking_rule"
    if _USE_HINT.search(haystack):
        return "use_matrix"
    if _DIMENSION_HINT.search(haystack):
        return "dimensional_rule"
    if _TABLE_HINT.search(text):
        return "table_text"
    if _FOOTNOTE_HINT.search(text):
        return "footnote"
    return "section_text"


def _token_estimate(text: str) -> int:
    return max(1, math.ceil(len(text.split()) * 1.25))


def chunk_sections(sections: list[LegalSection], max_chars: int = 1200) -> list[LegalChunk]:
    """Split legal sections into semantically coherent chunks with lightweight typing."""
    chunks: list[LegalChunk] = []
    for section in sections:
        current = ""
        chunk_index = 0
        for paragraph in _paragraphs(section.body_text):
            candidate = paragraph if not current else f"{current}\n\n{paragraph}"
            if current and len(candidate) > max_chars:
                chunks.append(
                    LegalChunk(
                        legal_section_id=section.id,
                        source_document_id=section.source_document_id,
                        node_id=section.node_id,
                        chunk_index=chunk_index,
                        chunk_type=_chunk_type(section, current),
                        chunk_text=current,
                        token_estimate=_token_estimate(current),
                        title=section.title,
                        subtitle=section.subtitle,
                        section_path=section.section_path,
                        metadata_json={"section_type": section.section_type},
                    )
                )
                chunk_index += 1
                current = paragraph
            else:
                current = candidate

        if current:
            chunks.append(
                LegalChunk(
                    legal_section_id=section.id,
                    source_document_id=section.source_document_id,
                    node_id=section.node_id,
                    chunk_index=chunk_index,
                    chunk_type=_chunk_type(section, current),
                    chunk_text=current,
                    token_estimate=_token_estimate(current),
                    title=section.title,
                    subtitle=section.subtitle,
                    section_path=section.section_path,
                    metadata_json={"section_type": section.section_type},
                )
            )
    return chunks
