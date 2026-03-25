from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import logging
from pathlib import Path
import re
from typing import Iterable

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from zoning_agno.db.models import MuniNodeORM

logger = logging.getLogger(__name__)

OVERFLOW_PLACEHOLDER = "Content is too large for cell."
_PRIMARY_CONTENT_SELECTORS = [
    "main",
    "#main-content",
    ".content",
    ".codes-content",
    ".document-content",
    ".CodeContent",
]


@dataclass(slots=True)
class SupplementalMatch:
    text: str
    source: str
    score: int


@dataclass(slots=True)
class OverflowResolutionStats:
    source_document_id: int
    overflow_node_count: int
    resolved_node_count: int
    unresolved_node_count: int
    strategies_used: list[str]


def resolve_overflow_nodes(
    session: Session,
    source_document_id: int,
    *,
    supplemental_sources: Iterable[str] = (),
    force: bool = False,
) -> OverflowResolutionStats:
    """Patch Municode XLSX overflow rows using direct node fetches and optional supplemental PDFs."""
    query = select(MuniNodeORM).where(MuniNodeORM.source_document_id == source_document_id)
    nodes = session.scalars(query.order_by(MuniNodeORM.row_number)).all()
    if force:
        nodes = [
            node
            for node in nodes
            if node.content == OVERFLOW_PLACEHOLDER or (node.raw_payload_json or {}).get("overflow_resolution")
        ]
    else:
        nodes = [node for node in nodes if node.content == OVERFLOW_PLACEHOLDER]
    strategies_used: set[str] = set()
    resolved = 0
    pages = _load_all_supplemental_pages(supplemental_sources)

    for node in nodes:
        match = _resolve_node(node, pages)
        if match is None:
            continue
        node.content = match.text
        payload = dict(node.raw_payload_json or {})
        payload["overflow_resolution"] = {
            "strategy": match.source.split(":", 1)[0],
            "source": match.source,
            "score": match.score,
        }
        node.raw_payload_json = payload
        session.add(node)
        resolved += 1
        strategies_used.add(match.source.split(":", 1)[0])

    session.commit()
    return OverflowResolutionStats(
        source_document_id=source_document_id,
        overflow_node_count=len(nodes),
        resolved_node_count=resolved,
        unresolved_node_count=len(nodes) - resolved,
        strategies_used=sorted(strategies_used),
    )


def find_best_supplemental_text(
    pages: list[tuple[str, str]],
    *,
    title: str | None,
    subtitle: str | None,
    node_id: str | None,
) -> SupplementalMatch | None:
    """Pick the highest-confidence supplemental page text for a missing Municode node."""
    candidates: list[SupplementalMatch] = []
    title_norm = _normalize_anchor(title)
    subtitle_norm = _normalize_anchor(subtitle)
    node_tokens = _node_tokens(node_id)
    for source, text in pages:
        score = 0
        has_anchor_match = False
        text_norm = _normalize_anchor(text)
        if subtitle_norm and subtitle_norm in text_norm:
            score += 18
            has_anchor_match = True
        if title_norm and title_norm in text_norm:
            score += 12
            has_anchor_match = True
        for token in node_tokens:
            if token and token in text_norm:
                score += 1
        if "table" in text_norm and subtitle_norm and "matrix" in subtitle_norm:
            score += 2
        if has_anchor_match and score >= 18:
            expanded_text = _expand_pdf_context(
                pages,
                source=source,
                base_text=text,
                window=4 if subtitle_norm and "matrix" in subtitle_norm else 1,
            )
            candidates.append(SupplementalMatch(text=expanded_text, source=source, score=score))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item.score, len(item.text)), reverse=True)
    return candidates[0]


def _resolve_node(node: MuniNodeORM, pages: list[tuple[str, str]]) -> SupplementalMatch | None:
    direct_text = _fetch_municode_node_text(node.url)
    if direct_text:
        return SupplementalMatch(text=direct_text, source=f"municode:{node.url}", score=100)
    return find_best_supplemental_text(
        pages,
        title=node.title,
        subtitle=node.subtitle,
        node_id=node.node_id,
    )


def _fetch_municode_node_text(url: str | None) -> str | None:
    if not url:
        return None
    try:
        with httpx.Client(follow_redirects=True, timeout=30.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = client.get(url)
            response.raise_for_status()
    except Exception as exc:
        logger.debug("Municode direct fetch failed for %s: %s", url, exc)
        return None
    soup = BeautifulSoup(response.text, "lxml")
    for selector in _PRIMARY_CONTENT_SELECTORS:
        for element in soup.select(selector):
            text = _clean_text(element.get_text("\n", strip=True))
            if text and len(text) > 250 and OVERFLOW_PLACEHOLDER.lower() not in text.lower():
                return text
    return None


def _load_all_supplemental_pages(sources: Iterable[str]) -> list[tuple[str, str]]:
    pages: list[tuple[str, str]] = []
    for source in sources:
        pages.extend(_load_supplemental_pages(source))
    return pages


def _expand_pdf_context(
    pages: list[tuple[str, str]],
    *,
    source: str,
    base_text: str,
    window: int,
) -> str:
    match = re.match(r"^(pdf:.+)#page=(\d+)$", source)
    if not match:
        return _clean_text(base_text)
    base_source = match.group(1)
    center_page = int(match.group(2))
    selected: list[str] = []
    for page_source, page_text in pages:
        page_match = re.match(rf"^{re.escape(base_source)}#page=(\d+)$", page_source)
        if not page_match:
            continue
        page_number = int(page_match.group(1))
        if abs(page_number - center_page) <= window:
            selected.append(_clean_text(page_text))
    return _clean_text("\n\n".join(selected) if selected else base_text)


def _load_supplemental_pages(source: str) -> list[tuple[str, str]]:
    raw_bytes = _read_binary_source(source)
    reader = PdfReader(BytesIO(raw_bytes))
    pages: list[tuple[str, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = _clean_text(page.extract_text() or "")
        if len(text) < 100:
            continue
        pages.append((f"pdf:{source}#page={index}", text))
    return pages


def _read_binary_source(source: str) -> bytes:
    if re.match(r"^https?://", source, re.IGNORECASE):
        with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(180.0), headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = client.get(source)
            response.raise_for_status()
            return response.content
    path = Path(source)
    return path.read_bytes()


def _clean_text(value: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", value.strip())


def _normalize_anchor(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _node_tokens(node_id: str | None) -> list[str]:
    if not node_id:
        return []
    pieces = re.split(r"[^A-Z0-9]+", node_id.upper())
    tokens: list[str] = []
    for piece in pieces:
        if not piece:
            continue
        if re.fullmatch(r"S\d+(?:\.\d+)+", piece):
            tokens.append(piece.lower().replace("s", "section "))
        if piece in {"AO", "RR", "RS", "RM", "GC", "GR", "NO", "NR", "CB", "MX", "MF", "MD", "MH", "LI", "HI", "HC", "CU", "PD"}:
            tokens.append(piece.lower())
    return tokens
