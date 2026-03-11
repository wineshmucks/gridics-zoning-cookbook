"""Zoning code crawl, normalization, chunking, and retrieval."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
import re
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from typing import Any, Callable
from urllib.parse import urljoin, urldefrag, urlparse

from sqlalchemy import delete, desc, func, select, text
from sqlalchemy.orm import Session

from app.db.models import (
    TenantClient,
    ZoningCodeDocument,
    ZoningCodeIngestionRun,
    ZoningCodeSection,
)
from app.core.config import settings
from app.services.tenant_service import ZONING_CODE_URL_SETTING_KEY
from app.services.compat import build_with_supported_kwargs

VECTOR_SCHEMA = "ai"
VECTOR_TABLE = "customer_zoning_chunks"
VECTOR_DIMENSIONS = settings.zoning_embedder_dimensions
MAX_CRAWL_PAGES = 40
MAX_CHUNK_CHARS = 1800
CHUNK_OVERLAP_CHARS = 240


@dataclass(slots=True)
class CrawledPage:
    url: str
    path: str
    title: str
    text: str
    sections: list["NormalizedSection"]
    status_code: int


@dataclass(slots=True)
class NormalizedSection:
    section_key: str
    title: str
    level: int
    order: int
    anchor: str | None
    path: str
    content: str
    metadata: dict[str, Any]


@dataclass(slots=True)
class ChunkedSection:
    id: str
    content_id: str
    name: str
    content: str
    metadata: dict[str, Any]
    content_hash: str


@dataclass(slots=True)
class _RateLimitState:
    lock: threading.Lock
    next_allowed_at: float = 0.0


@dataclass(slots=True)
class _GeminiGenAIEmbedder:
    """Compatibility embedder using google-genai directly."""

    id: str
    task_type: str
    dimensions: int
    api_key: str
    enable_batch: bool = True
    batch_size: int = 32

    def _response(self, text: str):
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("google-genai is not installed in the backend environment.") from exc

        model_id = self.id.removeprefix("models/")
        client = genai.Client(api_key=self.api_key)
        return client.models.embed_content(
            model=model_id,
            contents=text,
            config={
                "output_dimensionality": self.dimensions,
                "task_type": self.task_type,
            },
        )

    async def _async_response(self, contents: str | list[str]):
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("google-genai is not installed in the backend environment.") from exc

        model_id = self.id.removeprefix("models/")
        client = genai.Client(api_key=self.api_key)
        return await client.aio.models.embed_content(
            model=model_id,
            contents=contents,
            config={
                "output_dimensionality": self.dimensions,
                "task_type": self.task_type,
            },
        )

    @staticmethod
    def _extract_embedding(response) -> list[float]:
        embeddings = getattr(response, "embeddings", None) or []
        if not embeddings:
            return []
        values = getattr(embeddings[0], "values", None)
        return list(values) if values is not None else []

    @staticmethod
    def _extract_usage(response) -> dict[str, Any] | None:
        metadata = getattr(response, "metadata", None)
        billable_character_count = getattr(metadata, "billable_character_count", None)
        if billable_character_count is None:
            return None
        return {"billable_character_count": billable_character_count}

    def get_embedding(self, text: str) -> list[float]:
        return self._extract_embedding(self._response(text))

    def get_embedding_and_usage(self, text: str) -> tuple[list[float], dict[str, Any] | None]:
        response = self._response(text)
        return self._extract_embedding(response), self._extract_usage(response)

    def get_embeddings_batch_and_usage(self, texts: list[str]) -> tuple[list[list[float]], list[dict[str, Any] | None]]:
        embeddings: list[list[float]] = []
        usages: list[dict[str, Any] | None] = []

        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i : i + self.batch_size]
            response = self._response(batch_texts)
            response_embeddings = getattr(response, "embeddings", None) or []
            usage = self._extract_usage(response)
            for j, _text in enumerate(batch_texts):
                values = getattr(response_embeddings[j], "values", None) if j < len(response_embeddings) else None
                embeddings.append(list(values) if values is not None else [])
                usages.append(usage)

        return embeddings, usages

    async def async_get_embedding(self, text: str) -> list[float]:
        return self._extract_embedding(await self._async_response(text))

    async def async_get_embedding_and_usage(self, text: str) -> tuple[list[float], dict[str, Any] | None]:
        response = await self._async_response(text)
        return self._extract_embedding(response), self._extract_usage(response)

    async def async_get_embeddings_batch_and_usage(
        self,
        texts: list[str],
    ) -> tuple[list[list[float]], list[dict[str, Any] | None]]:
        embeddings: list[list[float]] = []
        usages: list[dict[str, Any] | None] = []

        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i : i + self.batch_size]
            response = await self._async_response(batch_texts)
            response_embeddings = getattr(response, "embeddings", None) or []
            usage = self._extract_usage(response)
            for j, _text in enumerate(batch_texts):
                values = getattr(response_embeddings[j], "values", None) if j < len(response_embeddings) else None
                embeddings.append(list(values) if values is not None else [])
                usages.append(usage)

        return embeddings, usages


_embedder_rate_limit_states: dict[str, _RateLimitState] = {}
_embedder_rate_limit_states_lock = threading.Lock()


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _clean_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value


def _normalize_multiline_text(value: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def get_tenant_zoning_code_url(tenant_client: TenantClient) -> str | None:
    settings_json = tenant_client.settings_json or {}
    value = settings_json.get(ZONING_CODE_URL_SETTING_KEY) if isinstance(settings_json, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def build_zoning_knowledge_status(db: Session, tenant_client: TenantClient) -> dict[str, Any]:
    latest_run = None
    document_count = 0
    section_count = 0

    try:
        latest_run = db.scalar(
            select(ZoningCodeIngestionRun)
            .where(ZoningCodeIngestionRun.tenant_client_id == tenant_client.id)
            .order_by(desc(ZoningCodeIngestionRun.started_at))
            .limit(1)
        )
        document_count = db.scalar(
            select(func.count())
            .select_from(ZoningCodeDocument)
            .where(ZoningCodeDocument.tenant_client_id == tenant_client.id)
        ) or 0
        section_count = db.scalar(
            select(func.count())
            .select_from(ZoningCodeSection)
            .where(ZoningCodeSection.tenant_client_id == tenant_client.id)
        ) or 0
    except Exception:
        latest_run = None
        document_count = 0
        section_count = 0

    chunk_count = 0
    try:
        chunk_count = db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM {VECTOR_SCHEMA}.{VECTOR_TABLE}
                WHERE meta_data @> CAST(:metadata AS jsonb)
                """
            ),
            {"metadata": f'{{"client_id": "{tenant_client.client_id}"}}'},
        ).scalar_one()
    except Exception:
        chunk_count = 0

    return {
        "client_id": tenant_client.client_id,
        "zoning_code_url": get_tenant_zoning_code_url(tenant_client),
        "documents": int(document_count),
        "sections": int(section_count),
        "chunks": int(chunk_count),
        "latest_run": (
            {
                "id": latest_run.id,
                "mode": latest_run.mode,
                "status": latest_run.status,
                "source_url": latest_run.source_url,
                "pages_crawled": latest_run.pages_crawled,
                "documents_extracted": latest_run.documents_extracted,
                "sections_extracted": latest_run.sections_extracted,
                "chunks_upserted": latest_run.chunks_upserted,
                "error_message": latest_run.error_message,
                "started_at": latest_run.started_at,
                "completed_at": latest_run.completed_at,
            }
            if latest_run
            else None
        ),
    }


def _require_bs4():
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("beautifulsoup4 is required for zoning code ingestion.") from exc
    return BeautifulSoup


def _build_same_site_scope(start_url: str) -> tuple[str, str]:
    parsed = urlparse(start_url)
    base_path = parsed.path or "/"
    if not base_path.endswith("/"):
        base_path = base_path.rsplit("/", 1)[0] or "/"
    return parsed.netloc.lower(), base_path


def _is_codehub_source(start_url: str) -> bool:
    host = urlparse(start_url).netloc.lower()
    return host == "codehub.gridics.com"


def _normalize_codehub_alias(start_url: str) -> str:
    alias = urlparse(start_url).path.strip() or "/"
    if not alias.startswith("/"):
        alias = f"/{alias}"
    return alias.rstrip("/") or "/"


def _extract_codehub_bootstrap_settings(html: str) -> dict[str, Any] | None:
    match = re.search(
        r'<script[^>]*type="application/json"[^>]*data-drupal-selector="drupal-settings-json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _codehub_title_from_settings(settings_json: dict[str, Any] | None, *, fallback: str) -> str:
    if not isinstance(settings_json, dict):
        return fallback
    page_data = settings_json.get("pageData")
    if isinstance(page_data, dict):
        for key in ("name", "fieldZoneiqTitle"):
            value = page_data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return fallback


def _html_to_text(html_fragment: str) -> str:
    if not html_fragment:
        return ""
    BeautifulSoup = _require_bs4()
    soup = BeautifulSoup(html_fragment, "html.parser")
    return _normalize_multiline_text(unescape(soup.get_text("\n")))


def _should_visit(url: str, *, allowed_host: str, base_path: str, seen: set[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.lower() != allowed_host:
        return False
    if not parsed.path.startswith(base_path):
        return False
    if url in seen:
        return False
    if any(parsed.path.lower().endswith(ext) for ext in (".pdf", ".doc", ".docx", ".jpg", ".png", ".zip")):
        return False
    return True


def crawl_zoning_code_site(
    start_url: str,
    *,
    max_pages: int = MAX_CRAWL_PAGES,
    progress_callback: Callable[[int], None] | None = None,
) -> list[CrawledPage]:
    if _is_codehub_source(start_url):
        return crawl_codehub_site(start_url, progress_callback=progress_callback)

    BeautifulSoup = _require_bs4()
    import requests

    allowed_host, base_path = _build_same_site_scope(start_url)
    session = requests.Session()
    session.headers.update({"User-Agent": "UZoneZoningKnowledgeBot/1.0"})

    queue: deque[str] = deque([urldefrag(start_url)[0]])
    seen: set[str] = set()
    pages: list[CrawledPage] = []

    while queue and len(pages) < max_pages:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)

        response = session.get(current, timeout=30)
        if response.status_code >= 400:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "form"]):
            tag.decompose()

        page = extract_page_content(current, response.status_code, soup)
        if page.text:
            pages.append(page)
            if progress_callback is not None:
                progress_callback(len(pages))

        for anchor in soup.find_all("a", href=True):
            next_url = urldefrag(urljoin(current, anchor["href"]))[0]
            if _should_visit(next_url, allowed_host=allowed_host, base_path=base_path, seen=seen):
                queue.append(next_url)

    return pages


def crawl_codehub_site(start_url: str, *, progress_callback: Callable[[int], None] | None = None) -> list[CrawledPage]:
    import requests

    session = requests.Session()
    session.headers.update({"User-Agent": "UZoneZoningKnowledgeBot/1.0"})

    source_response = session.get(start_url, timeout=30)
    source_response.raise_for_status()
    source_settings = _extract_codehub_bootstrap_settings(source_response.text)
    source_title = _codehub_title_from_settings(source_settings, fallback=start_url)

    alias = _normalize_codehub_alias(start_url)
    api_response = session.get(
        "https://codehub.gridics.com/api/v1/codehub/0",
        params={"alias": alias, "_format": "json"},
        timeout=30,
    )
    api_response.raise_for_status()
    items = api_response.json()

    page = extract_codehub_page_content(
        start_url,
        alias=alias,
        source_title=source_title,
        status_code=api_response.status_code,
        items=items,
    )
    if page.text and progress_callback is not None:
        progress_callback(1)
    return [page] if page.text else []


def extract_codehub_page_content(
    url: str,
    *,
    alias: str,
    source_title: str,
    status_code: int,
    items: list[dict[str, Any]],
) -> CrawledPage:
    indexed_items = {str(item.get("id")): item for item in items if item.get("id")}
    children_by_parent: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        parent_id = (item.get("ref") or {}).get("parent")
        if parent_id:
            children_by_parent.setdefault(str(parent_id), []).append(item)

    def is_heading(item: dict[str, Any]) -> bool:
        tag = ((item.get("li_attr") or {}).get("tag") or "").lower()
        return tag in {"h1", "h2", "h3", "h4", "h5", "h6"}

    def heading_level(item: dict[str, Any]) -> int:
        tag = ((item.get("li_attr") or {}).get("tag") or "").lower()
        if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
            return int(tag[1])
        return 1

    def heading_title(item: dict[str, Any]) -> str:
        return _clean_text(str(item.get("text") or ""))

    def heading_path(item: dict[str, Any]) -> str:
        titles: list[str] = []
        current = item
        seen: set[str] = set()
        while current:
            current_id = str(current.get("id") or "")
            if current_id in seen:
                break
            seen.add(current_id)
            if is_heading(current):
                title = heading_title(current)
                if title:
                    titles.append(title)
            parent_id = (current.get("ref") or {}).get("parent")
            current = indexed_items.get(str(parent_id)) if parent_id else None
        titles.reverse()
        return " > ".join(titles) or source_title

    def collect_body_texts(item_id: str) -> list[str]:
        body_texts: list[str] = []
        for child in children_by_parent.get(item_id, []):
            if is_heading(child):
                continue
            text = _html_to_text(str(child.get("text") or ""))
            if text:
                body_texts.append(text)
            child_id = child.get("id")
            if child_id:
                body_texts.extend(collect_body_texts(str(child_id)))
        return body_texts

    sections: list[NormalizedSection] = []
    order = 0
    for item in items:
        if not is_heading(item):
            continue
        item_id = item.get("id")
        if not item_id:
            continue
        title = heading_title(item)
        body_texts = collect_body_texts(str(item_id))
        content = "\n".join(part for part in body_texts if part).strip()
        if not title or not content:
            continue
        path = heading_path(item)
        sections.append(
            NormalizedSection(
                section_key=f"{url}#{item_id}",
                title=title,
                level=heading_level(item),
                order=order,
                anchor=str(item_id),
                path=path,
                content=content,
                metadata={
                    "source_url": url,
                    "section_title": title,
                    "section_level": heading_level(item),
                    "source_anchor": str(item_id),
                    "section_path": path,
                    "source_path": str(item.get("path") or alias),
                    "source_system": "codehub",
                    "codehub_doc_id": str(item.get("docId") or ""),
                },
            )
        )
        order += 1

    page_text = "\n\n".join(f"{section.title}\n{section.content}" for section in sections).strip()
    return CrawledPage(
        url=url,
        path=alias,
        title=source_title,
        text=page_text,
        sections=sections,
        status_code=status_code,
    )


def extract_page_content(url: str, status_code: int, soup) -> CrawledPage:
    container = soup.find("main") or soup.find("article") or soup.body or soup
    for selector in ("nav", "header", "footer", "aside"):
        for tag in container.find_all(selector):
            tag.decompose()

    title = _clean_text((soup.title.string if soup.title and soup.title.string else "") or "")
    text = _normalize_multiline_text(container.get_text("\n"))
    sections = normalize_legal_sections(url, container, default_title=title or url)
    parsed = urlparse(url)
    return CrawledPage(
        url=url,
        path=parsed.path or "/",
        title=title or url,
        text=text,
        sections=sections,
        status_code=status_code,
    )


def normalize_legal_sections(url: str, container, *, default_title: str) -> list[NormalizedSection]:
    heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
    section_nodes = container.find_all(list(heading_tags) + ["p", "li", "blockquote", "td", "th"])
    sections: list[NormalizedSection] = []
    current_title = default_title
    current_level = 1
    current_anchor: str | None = None
    current_lines: list[str] = []
    current_path = default_title
    order = 0

    def flush_section() -> None:
        nonlocal order
        content = "\n".join(line for line in current_lines if line).strip()
        if not content:
            return
        section_key = f"{url}#{current_anchor or order}"
        sections.append(
            NormalizedSection(
                section_key=section_key,
                title=current_title,
                level=current_level,
                order=order,
                anchor=current_anchor,
                path=current_path,
                content=content,
                metadata={
                    "source_url": url,
                    "section_title": current_title,
                    "section_level": current_level,
                    "source_anchor": current_anchor,
                    "section_path": current_path,
                },
            )
        )
        order += 1

    for node in section_nodes:
        text = _clean_text(node.get_text(" ", strip=True))
        if not text:
            continue
        if node.name in heading_tags:
            flush_section()
            current_lines = []
            current_title = text
            current_level = int(node.name[1])
            current_anchor = node.get("id") or node.get("data-anchor")
            current_path = f"{default_title} > {current_title}" if current_title != default_title else default_title
            continue
        if text not in current_lines:
            current_lines.append(text)

    flush_section()
    if sections:
        return sections
    fallback_text = _normalize_multiline_text(container.get_text("\n"))
    if not fallback_text:
        return []
    return [
        NormalizedSection(
            section_key=f"{url}#0",
            title=default_title,
            level=1,
            order=0,
            anchor=None,
            path=default_title,
            content=fallback_text,
            metadata={
                "source_url": url,
                "section_title": default_title,
                "section_level": 1,
                "section_path": default_title,
            },
        )
    ]


def chunk_normalized_section(
    tenant_client: TenantClient,
    document: ZoningCodeDocument,
    section: NormalizedSection,
    *,
    max_chars: int = MAX_CHUNK_CHARS,
    overlap_chars: int = CHUNK_OVERLAP_CHARS,
) -> list[ChunkedSection]:
    paragraphs = [part.strip() for part in section.content.split("\n") if part.strip()]
    chunks: list[ChunkedSection] = []
    current = ""
    index = 0

    def build_chunk(content: str) -> ChunkedSection:
        chunk_id = str(uuid.uuid4())
        content_hash = _hash_text(f"{section.section_key}:{content}")
        return ChunkedSection(
            id=chunk_id,
            content_id=section.section_key,
            name=f"{tenant_client.city_name} zoning code",
            content=content,
            metadata={
                "client_id": tenant_client.client_id,
                "tenant_client_id": tenant_client.id,
                "document_id": document.id,
                "source_url": document.source_url,
                "source_title": document.source_title,
                "section_key": section.section_key,
                "section_title": section.title,
                "section_order": section.order,
                "section_level": section.level,
                "section_path": section.path,
                "source_anchor": section.anchor,
                "chunk_index": index,
            },
            content_hash=content_hash,
        )

    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n{paragraph}"
        if current and len(candidate) > max_chars:
            chunks.append(build_chunk(current))
            index += 1
            overlap = current[-overlap_chars:] if overlap_chars else ""
            current = f"{overlap}\n{paragraph}".strip()
        else:
            current = candidate

    if current:
        chunks.append(build_chunk(current))

    return chunks


def _require_embedder_dimensions() -> int:
    dimensions = settings.zoning_embedder_dimensions
    if dimensions <= 0:
        raise ValueError("UZONE_ZONING_EMBEDDER_DIMENSIONS must be greater than zero.")
    return dimensions


def _get_embedder_api_key(provider: str) -> str | None:
    if settings.zoning_embedder_api_key:
        return settings.zoning_embedder_api_key

    if provider == "gemini":
        return os.getenv("GOOGLE_API_KEY", "").strip() or None
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY", "").strip() or None
    if provider == "openrouter":
        return os.getenv("OPENROUTER_API_KEY", "").strip() or None
    return None


def _rate_limit_key(provider: str, model_id: str) -> str:
    return f"{provider}:{model_id}"


def _get_rate_limit_state(key: str) -> _RateLimitState:
    with _embedder_rate_limit_states_lock:
        state = _embedder_rate_limit_states.get(key)
        if state is None:
            state = _RateLimitState(lock=threading.Lock())
            _embedder_rate_limit_states[key] = state
        return state


class RateLimitedEmbedder:
    def __init__(self, embedder, *, requests_per_minute: float, key: str):
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be greater than zero")
        self.embedder = embedder
        self.requests_per_minute = requests_per_minute
        self.min_interval_seconds = 60.0 / requests_per_minute
        self.state = _get_rate_limit_state(key)

    def _wait_for_slot(self) -> None:
        with self.state.lock:
            now = time.monotonic()
            if self.state.next_allowed_at > now:
                time.sleep(self.state.next_allowed_at - now)
                now = time.monotonic()
            self.state.next_allowed_at = now + self.min_interval_seconds

    def get_embedding(self, text: str):
        self._wait_for_slot()
        return self.embedder.get_embedding(text)

    def get_embedding_and_usage(self, text: str):
        self._wait_for_slot()
        return self.embedder.get_embedding_and_usage(text)

    def get_embeddings_batch_and_usage(self, texts: list[str]):
        self._wait_for_slot()
        return self.embedder.get_embeddings_batch_and_usage(texts)

    async def async_get_embedding(self, text: str):
        self._wait_for_slot()
        return await self.embedder.async_get_embedding(text)

    async def async_get_embedding_and_usage(self, text: str):
        self._wait_for_slot()
        return await self.embedder.async_get_embedding_and_usage(text)

    async def async_get_embeddings_batch_and_usage(self, texts: list[str]):
        self._wait_for_slot()
        return await self.embedder.async_get_embeddings_batch_and_usage(texts)

    def __getattr__(self, name: str):
        return getattr(self.embedder, name)


def _maybe_rate_limit_embedder(embedder, *, provider: str, model_id: str):
    requests_per_minute = settings.zoning_embedder_requests_per_minute
    if requests_per_minute <= 0:
        return embedder
    return RateLimitedEmbedder(
        embedder,
        requests_per_minute=requests_per_minute,
        key=_rate_limit_key(provider, model_id),
    )


def _build_embedder_pair():
    provider = settings.zoning_embedder_provider.strip().lower()
    model_id = settings.zoning_embedder_model_id.strip()
    dimensions = _require_embedder_dimensions()
    api_key = _get_embedder_api_key(provider)

    if provider == "gemini":
        if not api_key:
            raise ValueError(
                "Set UZONE_ZONING_EMBEDDER_API_KEY or GOOGLE_API_KEY for the Gemini zoning embedder."
            )
        try:
            from agno.knowledge.embedder.google import GeminiEmbedder
        except ImportError:
            try:
                from agno.embedder.google import GeminiEmbedder
            except ImportError:
                GeminiEmbedder = _GeminiGenAIEmbedder

        query_embedder = GeminiEmbedder(
            dimensions=dimensions,
            enable_batch=True,
            batch_size=32,
            id=model_id,
            task_type="RETRIEVAL_QUERY",
            api_key=api_key,
        )
        document_embedder = GeminiEmbedder(
            dimensions=dimensions,
            enable_batch=True,
            batch_size=32,
            id=model_id,
            task_type="RETRIEVAL_DOCUMENT",
            api_key=api_key,
        )
        return (
            _maybe_rate_limit_embedder(query_embedder, provider=provider, model_id=model_id),
            _maybe_rate_limit_embedder(document_embedder, provider=provider, model_id=model_id),
        )

    if provider in {"openai", "openrouter"}:
        if not api_key:
            env_name = "OPENAI_API_KEY" if provider == "openai" else "OPENROUTER_API_KEY"
            raise ValueError(
                f"Set UZONE_ZONING_EMBEDDER_API_KEY or {env_name} for the {provider} zoning embedder."
            )
        try:
            from agno.knowledge.embedder.openai import OpenAIEmbedder
        except ImportError as exc:  # pragma: no cover - dependency guard
            try:
                from agno.embedder.openai import OpenAIEmbedder
            except ImportError:
                raise RuntimeError(
                    "OpenAI-compatible embedder support is not installed in the backend environment."
                ) from exc

        base_url = settings.zoning_embedder_base_url
        if provider == "openrouter" and not base_url:
            base_url = "https://openrouter.ai/api/v1"

        common_kwargs = {
            "dimensions": dimensions,
            "enable_batch": True,
            "batch_size": 32,
            "id": model_id,
            "api_key": api_key,
            "base_url": base_url,
        }
        query_embedder = build_with_supported_kwargs(OpenAIEmbedder, **common_kwargs)
        document_embedder = build_with_supported_kwargs(OpenAIEmbedder, **common_kwargs)
        return (
            _maybe_rate_limit_embedder(query_embedder, provider=provider, model_id=model_id),
            _maybe_rate_limit_embedder(document_embedder, provider=provider, model_id=model_id),
        )

    raise ValueError(
        f"Unsupported UZONE_ZONING_EMBEDDER_PROVIDER '{provider}'. "
        "Supported providers: gemini, openai, openrouter."
    )


class CustomerZoningPgVectorMixin:
    def __init__(self, *, document_embedder, query_embedder, **kwargs):
        self.document_embedder = document_embedder
        super().__init__(embedder=query_embedder, **kwargs)

    def _get_document_record(self, doc, filters=None, content_hash: str = ""):
        doc.embed(embedder=self.document_embedder)
        cleaned_content = self._clean_content(doc.content)
        base_id = doc.id or hashlib.md5(cleaned_content.encode()).hexdigest()
        record_id = hashlib.md5(f"{base_id}_{content_hash}".encode()).hexdigest()
        meta_data = doc.meta_data or {}
        if filters:
            meta_data.update(filters)
        record = {
            "id": record_id,
            "name": doc.name,
            "meta_data": meta_data,
            "filters": filters,
            "content": cleaned_content,
            "embedding": doc.embedding,
            "usage": doc.usage,
            "content_hash": content_hash,
        }
        table_columns = getattr(getattr(self, "table", None), "c", None)
        if table_columns is None or "content_id" in table_columns:
            record["content_id"] = getattr(doc, "content_id", None)
        return record


def _build_vector_db():
    try:
        from agno.vectordb.pgvector import PgVector
        from agno.vectordb.search import SearchType
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError(
            "Agno pgvector dependencies are required. Install pgvector and agno extras in the backend environment."
        ) from exc

    query_embedder, document_embedder = _build_embedder_pair()

    class CustomerZoningPgVector(CustomerZoningPgVectorMixin, PgVector):
        pass

    return build_with_supported_kwargs(
        CustomerZoningPgVector,
        document_embedder=document_embedder,
        query_embedder=query_embedder,
        table_name=VECTOR_TABLE,
        schema=VECTOR_SCHEMA,
        db_url=settings.database_url,
        search_type=SearchType.hybrid,
        create_schema=False,
    )


def build_customer_zoning_knowledge():
    from agno.knowledge.knowledge import Knowledge

    vector_db = _build_vector_db()
    return Knowledge(
        name="customer-zoning-knowledge",
        description="Customer zoning code knowledge base",
        vector_db=vector_db,
        max_results=8,
    )


def _build_vector_db_with_engine(db: Session):
    try:
        from agno.vectordb.pgvector import PgVector
        from agno.vectordb.search import SearchType
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError(
            "Agno pgvector dependencies are required. Install pgvector and agno extras in the backend environment."
        ) from exc

    query_embedder, document_embedder = _build_embedder_pair()

    class CustomerZoningPgVector(CustomerZoningPgVectorMixin, PgVector):
        pass

    return build_with_supported_kwargs(
        CustomerZoningPgVector,
        document_embedder=document_embedder,
        query_embedder=query_embedder,
        table_name=VECTOR_TABLE,
        schema=VECTOR_SCHEMA,
        db_engine=db.get_bind(),
        search_type=SearchType.hybrid,
        create_schema=False,
    )


def _to_agno_documents(chunks: list[ChunkedSection]):
    from agno.knowledge.document import Document

    return [
        build_with_supported_kwargs(
            Document,
            id=chunk.id,
            name=chunk.name,
            content=chunk.content,
            meta_data=chunk.metadata,
            content_id=chunk.content_id,
        )
        for chunk in chunks
    ]


def _validate_crawl_output(
    source_url: str,
    pages: list[CrawledPage],
    chunks: list[ChunkedSection],
) -> None:
    if not pages:
        raise RuntimeError(
            "No static zoning-code pages were extracted from the configured source URL. "
            f"The site at {source_url} appears to load content dynamically, which this ingester "
            "does not currently crawl."
        )
    if not chunks:
        raise RuntimeError(
            "Zoning-code pages were fetched, but no section content was extracted into chunks."
        )


def _delete_vector_rows_for_client(db: Session, client_id: str, vector_db: Any | None = None) -> None:
    if vector_db is not None and hasattr(vector_db, "delete_by_metadata"):
        vector_db.delete_by_metadata({"client_id": client_id})
        return

    db.execute(
        text(
            f"""
            DELETE FROM {VECTOR_SCHEMA}.{VECTOR_TABLE}
            WHERE meta_data @> CAST(:metadata AS jsonb)
            """
        ),
        {"metadata": json.dumps({"client_id": client_id})},
    )


def _upsert_vector_documents(
    vector_db: Any,
    *,
    documents: list[Any],
    client_id: str,
    content_hash: str,
) -> None:
    kwargs = {
        "content_hash": content_hash,
        "documents": documents,
        "filters": {"client_id": client_id},
    }
    if hasattr(vector_db, "async_upsert"):
        asyncio.run(_async_call_with_supported_kwargs(vector_db.async_upsert, **kwargs))
        return

    build_with_supported_kwargs(
        vector_db.upsert,
        content_hash=content_hash,
        documents=documents,
        filters={"client_id": client_id},
    )


def _filter_supported_kwargs(factory: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    try:
        signature = inspect.signature(factory)
    except (TypeError, ValueError):
        return kwargs

    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
        return kwargs

    supported_names = {
        name
        for name, param in signature.parameters.items()
        if param.kind in {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}
    }
    return {key: value for key, value in kwargs.items() if key in supported_names}


async def _async_call_with_supported_kwargs(factory: Any, **kwargs: Any) -> Any:
    return await factory(**_filter_supported_kwargs(factory, kwargs))


def _delete_existing_corpus(db: Session, tenant_client: TenantClient) -> None:
    vector_db = _build_vector_db_with_engine(db)
    _delete_vector_rows_for_client(db, tenant_client.client_id, vector_db)
    db.execute(delete(ZoningCodeSection).where(ZoningCodeSection.tenant_client_id == tenant_client.id))
    db.execute(delete(ZoningCodeDocument).where(ZoningCodeDocument.tenant_client_id == tenant_client.id))


def _update_ingestion_run(
    db: Session,
    run: ZoningCodeIngestionRun,
    **fields: Any,
) -> None:
    for key, value in fields.items():
        setattr(run, key, value)
    db.add(run)
    db.commit()
    db.refresh(run)


def start_zoning_code_ingestion(
    db: Session,
    tenant_client: TenantClient,
    *,
    mode: str,
) -> ZoningCodeIngestionRun:
    source_url = get_tenant_zoning_code_url(tenant_client)
    if not source_url:
        raise ValueError("Set a zoning code URL for this customer before ingesting.")

    if mode not in {"ingest", "reindex"}:
        raise ValueError("mode must be 'ingest' or 'reindex'")

    existing_run = db.scalar(
        select(ZoningCodeIngestionRun)
        .where(
            ZoningCodeIngestionRun.tenant_client_id == tenant_client.id,
            ZoningCodeIngestionRun.status.in_(("queued", "running")),
        )
        .order_by(desc(ZoningCodeIngestionRun.started_at))
        .limit(1)
    )
    if existing_run is not None:
        raise ValueError("A zoning knowledge ingestion run is already in progress for this customer.")

    run = ZoningCodeIngestionRun(
        tenant_client_id=tenant_client.id,
        mode=mode,
        status="queued",
        source_url=source_url,
        started_at=_utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def run_zoning_code_ingestion(run_id: str) -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        run = db.get(ZoningCodeIngestionRun, run_id)
        if run is None:
            return
        tenant_client = db.get(TenantClient, run.tenant_client_id)
        if tenant_client is None:
            _update_ingestion_run(
                db,
                run,
                status="failed",
                error_message="Tenant client not found for ingestion run.",
                completed_at=_utcnow(),
            )
            return

        _update_ingestion_run(
            db,
            run,
            status="running",
            error_message=None,
            completed_at=None,
            pages_crawled=0,
            documents_extracted=0,
            sections_extracted=0,
            chunks_upserted=0,
        )

        if run.mode == "reindex":
            _delete_existing_corpus(db, tenant_client)
            db.commit()

        pages = crawl_zoning_code_site(
            run.source_url,
            progress_callback=lambda count: _update_ingestion_run(db, run, pages_crawled=count),
        )
        vector_db = _build_vector_db_with_engine(db)
        all_chunks: list[ChunkedSection] = []
        documents_extracted = 0
        sections_extracted = 0

        for page in pages:
            source_hash = _hash_text(page.text)
            document = db.scalar(
                select(ZoningCodeDocument).where(
                    ZoningCodeDocument.tenant_client_id == tenant_client.id,
                    ZoningCodeDocument.source_url == page.url,
                )
            )
            if document is None:
                document = ZoningCodeDocument(
                    tenant_client_id=tenant_client.id,
                    ingestion_run_id=run.id,
                    source_url=page.url,
                    source_path=page.path,
                    source_title=page.title,
                    source_hash=source_hash,
                    fetch_status_code=page.status_code,
                    raw_text=page.text,
                    metadata_json={"title": page.title},
                    fetched_at=_utcnow(),
                )
                db.add(document)
                db.flush()
            else:
                document.ingestion_run_id = run.id
                document.source_path = page.path
                document.source_title = page.title
                document.source_hash = source_hash
                document.fetch_status_code = page.status_code
                document.raw_text = page.text
                document.metadata_json = {"title": page.title}
                document.fetched_at = _utcnow()
                db.flush()

            for section in page.sections:
                section_hash = _hash_text(f"{document.source_url}:{section.title}:{section.content}")
                existing_section = db.scalar(
                    select(ZoningCodeSection).where(
                        ZoningCodeSection.tenant_client_id == tenant_client.id,
                        ZoningCodeSection.section_key == section.section_key,
                    )
                )
                if existing_section is None:
                    existing_section = ZoningCodeSection(
                        tenant_client_id=tenant_client.id,
                        ingestion_run_id=run.id,
                        document_id=document.id,
                        section_key=section.section_key,
                        section_title=section.title,
                        section_level=section.level,
                        section_order=section.order,
                        section_path=section.path,
                        normalized_text=section.content,
                        source_anchor=section.anchor,
                        metadata_json=section.metadata,
                        content_hash=section_hash,
                    )
                    db.add(existing_section)
                else:
                    existing_section.ingestion_run_id = run.id
                    existing_section.document_id = document.id
                    existing_section.section_title = section.title
                    existing_section.section_level = section.level
                    existing_section.section_order = section.order
                    existing_section.section_path = section.path
                    existing_section.normalized_text = section.content
                    existing_section.source_anchor = section.anchor
                    existing_section.metadata_json = section.metadata
                    existing_section.content_hash = section_hash
                db.flush()

                all_chunks.extend(chunk_normalized_section(tenant_client, document, section))

            documents_extracted += 1
            sections_extracted += len(page.sections)
            _update_ingestion_run(
                db,
                run,
                documents_extracted=documents_extracted,
                sections_extracted=sections_extracted,
            )

        _validate_crawl_output(run.source_url, pages, all_chunks)

        if all_chunks:
            agno_documents = _to_agno_documents(all_chunks)
            # Delete current tenant corpus to avoid duplicate chunks across incremental runs.
            _delete_vector_rows_for_client(db, tenant_client.client_id, vector_db)
            _upsert_vector_documents(
                vector_db,
                documents=agno_documents,
                client_id=tenant_client.client_id,
                content_hash=f"{tenant_client.client_id}:{run.id}",
            )

        _update_ingestion_run(
            db,
            run,
            status="completed",
            pages_crawled=len(pages),
            documents_extracted=len(pages),
            sections_extracted=sum(len(page.sections) for page in pages),
            chunks_upserted=len(all_chunks),
            completed_at=_utcnow(),
        )
    except Exception as exc:
        db.rollback()
        if "run" in locals() and run is not None:
            _update_ingestion_run(
                db,
                run,
                status="failed",
                error_message=str(exc),
                completed_at=_utcnow(),
            )
    finally:
        db.close()


def ingest_customer_zoning_code(
    db: Session,
    tenant_client: TenantClient,
    *,
    mode: str,
) -> dict[str, Any]:
    start_zoning_code_ingestion(db, tenant_client, mode=mode)
    return build_zoning_knowledge_status(db, tenant_client)


def query_customer_zoning_knowledge(
    db: Session,
    tenant_client: TenantClient,
    *,
    query: str,
    limit: int = 5,
) -> dict[str, Any]:
    if not query.strip():
        raise ValueError("Query text is required.")

    from agno.knowledge.knowledge import Knowledge

    vector_db = _build_vector_db_with_engine(db)
    knowledge = Knowledge(
        name=f"customer-zoning-{tenant_client.client_id}",
        description=f"{tenant_client.city_name} zoning knowledge",
        vector_db=vector_db,
        max_results=limit,
    )
    documents = knowledge.search(query=query.strip(), max_results=limit, filters={"client_id": tenant_client.client_id})
    return {
        "query": query.strip(),
        "results": [
            {
                "content": item.content,
                "name": item.name,
                "meta_data": item.meta_data,
            }
            for item in documents
        ],
    }
