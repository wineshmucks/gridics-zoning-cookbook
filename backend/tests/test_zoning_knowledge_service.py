"""Unit tests for zoning knowledge normalization, chunking, and embedder config."""

import asyncio
import sys
import types
from pathlib import Path
import re
from types import SimpleNamespace

from app.db.models import ZoningCodeDocument
from app.services.zoning_knowledge_service import (
    CustomerZoningPgVectorMixin,
    NormalizedSection,
    RateLimitedEmbedder,
    VECTOR_DIMENSIONS,
    ChunkedSection,
    _GeminiGenAIEmbedder,
    _delete_vector_rows_for_client,
    _build_embedder_pair,
    _build_vector_db,
    _extract_codehub_bootstrap_settings,
    _is_codehub_source,
    _normalize_codehub_alias,
    _upsert_vector_documents,
    _to_agno_documents,
    _validate_crawl_output,
    build_zoning_knowledge_status,
    chunk_normalized_section,
    extract_codehub_page_content,
    get_tenant_zoning_code_url,
    query_customer_zoning_knowledge,
)


class DummyTenant:
    def __init__(self) -> None:
        self.id = "tenant-1"
        self.client_id = "tenant-1"
        self.city_name = "Test City"
        self.settings_json = {"zoning_code_url": "https://example.com/code"}


def test_get_tenant_zoning_code_url_reads_settings_json() -> None:
    tenant = DummyTenant()

    assert get_tenant_zoning_code_url(tenant) == "https://example.com/code"


def test_build_zoning_knowledge_status_includes_gemini_embedder_metadata(monkeypatch) -> None:
    tenant = DummyTenant()
    monkeypatch.setattr(
        "app.services.zoning_knowledge_service.settings.zoning_embedder_provider",
        "gemini",
    )
    monkeypatch.setattr(
        "app.services.zoning_knowledge_service.settings.zoning_embedder_model_id",
        "gemini-embedding-001",
    )
    monkeypatch.setattr(
        "app.services.zoning_knowledge_service.settings.zoning_embedder_dimensions",
        VECTOR_DIMENSIONS,
    )
    latest_run = SimpleNamespace(
        id="run-1",
        mode="ingest",
        status="completed",
        source_url="https://example.com/code",
        pages_crawled=1,
        documents_extracted=1,
        sections_extracted=1,
        chunks_upserted=1,
        error_message=None,
        started_at=SimpleNamespace(),
        completed_at=SimpleNamespace(),
    )

    class FakeDB:
        def __init__(self) -> None:
            self._scalar_calls = 0

        def scalar(self, *args, **kwargs):
            self._scalar_calls += 1
            if self._scalar_calls == 1:
                return latest_run
            return 2

        def execute(self, *args, **kwargs):
            return SimpleNamespace(scalar_one=lambda: 4)

    status = build_zoning_knowledge_status(FakeDB(), tenant)

    assert status["embedder_provider"] == "gemini"
    assert status["embedder_model_id"] == "gemini-embedding-001"
    assert status["embedder_dimensions"] == VECTOR_DIMENSIONS
    assert status["progress_percent"] == 100.0
    assert status["progress_message"] == "Ingestion complete."
    assert status["is_complete"] is True


def test_customer_zoning_chunk_schema_matches_embedder_dimensions() -> None:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "20260419_000014_rebuild_customer_zoning_chunks_for_1536_embeddings.py"
    )
    upgrade_block = migration_path.read_text(encoding="utf-8").split("def downgrade()", 1)[0]
    match = re.search(r"embedding vector\((\d+)\)", upgrade_block)

    assert match is not None, "Expected the customer zoning chunk migration to declare a vector dimension."
    assert int(match.group(1)) == VECTOR_DIMENSIONS


def test_query_customer_zoning_knowledge_returns_lookup_timing(monkeypatch) -> None:
    tenant = DummyTenant()

    class FakeKnowledge:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def search(self, *, query: str, max_results: int, filters: dict[str, str]):
            assert query == "height limits"
            assert max_results == 3
            assert filters == {"client_id": tenant.client_id}
            return [
                SimpleNamespace(
                    content="Max 35 feet",
                    name="Section 1",
                    meta_data={
                        "section": "1",
                        "source_url": "https://example.com/code",
                        "source_anchor": "section-1",
                        "section_url": "https://example.com/code#section-1",
                        "source_title": "Code Section",
                    },
                )
            ]

    knowledge_module = types.ModuleType("agno.knowledge.knowledge")
    knowledge_module.Knowledge = FakeKnowledge
    monkeypatch.setitem(sys.modules, "agno.knowledge.knowledge", knowledge_module)
    monkeypatch.setattr(
        "app.services.zoning_knowledge_service._build_vector_db_with_engine",
        lambda db: "vector-db",
    )

    timings = iter([10.0, 10.125])
    monkeypatch.setattr(
        "app.services.zoning_knowledge_service.time.perf_counter",
        lambda: next(timings),
    )

    result = query_customer_zoning_knowledge(object(), tenant, query="height limits", limit=3)

    assert result["query"] == "height limits"
    assert result["lookup_ms"] == 125.0
    assert result["results"] == [
        {
            "content": "Max 35 feet",
            "name": "Section 1",
            "page_url": "https://example.com/code",
            "section_url": "https://example.com/code#section-1",
            "source_title": "Code Section",
            "source_anchor": "section-1",
            "source_url": "https://example.com/code",
            "meta_data": {
                "section": "1",
                "source_url": "https://example.com/code",
                "source_anchor": "section-1",
                "section_url": "https://example.com/code#section-1",
                "source_title": "Code Section",
                "page_url": "https://example.com/code",
            },
        }
    ]


def test_chunk_normalized_section_splits_large_sections() -> None:
    tenant = DummyTenant()
    document = ZoningCodeDocument(
        id="doc-1",
        tenant_client_id=tenant.id,
        source_url="https://example.com/code/section-1",
        source_title="Code Section",
        source_hash="hash-1",
        raw_text="",
    )
    section = NormalizedSection(
        section_key="https://example.com/code/section-1#sec",
        title="Section 1",
        level=2,
        order=0,
        anchor="sec",
        path="Title 1 > Section 1",
        content="\n".join(["Paragraph " + ("x" * 400) for _ in range(8)]),
        metadata={"source_url": "https://example.com/code/section-1"},
    )

    chunks = chunk_normalized_section(tenant, document, section, max_chars=900, overlap_chars=50)

    assert len(chunks) >= 2
    assert all(chunk.metadata["client_id"] == tenant.client_id for chunk in chunks)
    assert all(chunk.metadata["section_title"] == "Section 1" for chunk in chunks)


def test_build_embedder_pair_rejects_non_gemini_provider(monkeypatch) -> None:
    monkeypatch.setattr("app.services.zoning_knowledge_service.settings.zoning_embedder_provider", "unsupported")
    monkeypatch.setattr(
        "app.services.zoning_knowledge_service.settings.zoning_embedder_model_id",
        "gemini-embedding-001",
    )
    monkeypatch.setattr(
        "app.services.zoning_knowledge_service.settings.zoning_embedder_dimensions",
        VECTOR_DIMENSIONS,
    )
    monkeypatch.setattr("app.services.zoning_knowledge_service.settings.zoning_embedder_api_key", "test-key")

    with pytest.raises(ValueError, match="Supported providers: gemini"):
        _build_embedder_pair()


def test_build_embedder_pair_falls_back_to_google_genai_for_gemini(monkeypatch) -> None:
    calls: list[dict] = []

    class FakeModels:
        def embed_content(self, **kwargs):
            calls.append(kwargs)

            class Response:
                embeddings = [types.SimpleNamespace(values=[0.1] * VECTOR_DIMENSIONS)]
                metadata = types.SimpleNamespace(billable_character_count=42)

            return Response()

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            self.models = FakeModels()

    monkeypatch.setattr("app.services.zoning_knowledge_service.settings.zoning_embedder_provider", "gemini")
    monkeypatch.setattr(
        "app.services.zoning_knowledge_service.settings.zoning_embedder_model_id",
        "gemini-embedding-001",
    )
    monkeypatch.setattr(
        "app.services.zoning_knowledge_service.settings.zoning_embedder_dimensions",
        VECTOR_DIMENSIONS,
    )
    monkeypatch.setattr("app.services.zoning_knowledge_service.settings.zoning_embedder_api_key", "test-key")
    monkeypatch.delitem(sys.modules, "agno.knowledge.embedder.google", raising=False)

    google_module = types.ModuleType("google")
    google_module.genai = types.SimpleNamespace(Client=FakeClient)
    monkeypatch.setitem(sys.modules, "google", google_module)

    query_embedder, document_embedder = _build_embedder_pair()
    vector, usage = query_embedder.get_embedding_and_usage("query text")

    assert document_embedder is not None
    assert vector == [0.1] * VECTOR_DIMENSIONS
    assert usage == {"billable_character_count": 42}
    assert calls[0]["model"] == "gemini-embedding-001"
    assert calls[0]["config"]["task_type"] == "RETRIEVAL_QUERY"
    assert calls[0]["config"]["output_dimensionality"] == VECTOR_DIMENSIONS


def test_gemini_genai_embedder_supports_async_batch(monkeypatch) -> None:
    calls: list[dict] = []

    class FakeAioModels:
        async def embed_content(self, **kwargs):
            calls.append(kwargs)
            return types.SimpleNamespace(
                embeddings=[
                    types.SimpleNamespace(values=[0.1, 0.2]),
                    types.SimpleNamespace(values=[0.3, 0.4]),
                ],
                metadata=types.SimpleNamespace(billable_character_count=11),
            )

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            self.aio = types.SimpleNamespace(models=FakeAioModels())

    google_module = types.ModuleType("google")
    google_module.genai = types.SimpleNamespace(Client=FakeClient)
    monkeypatch.setitem(sys.modules, "google", google_module)

    embedder = _GeminiGenAIEmbedder(
        id="gemini-embedding-001",
        task_type="RETRIEVAL_DOCUMENT",
        dimensions=VECTOR_DIMENSIONS,
        api_key="test-key",
        batch_size=2,
    )

    embeddings, usages = asyncio.run(embedder.async_get_embeddings_batch_and_usage(["one", "two"]))

    assert embeddings == [[0.1, 0.2], [0.3, 0.4]]
    assert usages == [{"billable_character_count": 11}, {"billable_character_count": 11}]
    assert calls[0]["contents"] == ["one", "two"]


def test_to_agno_documents_drops_unsupported_content_id(monkeypatch) -> None:
    class LegacyDocument:
        def __init__(self, *, content: str, id: str | None = None, name: str | None = None, meta_data=None) -> None:
            self.content = content
            self.id = id
            self.name = name
            self.meta_data = meta_data or {}

    document_module = types.ModuleType("agno.knowledge.document")
    document_module.Document = LegacyDocument
    monkeypatch.setitem(sys.modules, "agno.knowledge.document", document_module)

    chunks = [
        ChunkedSection(
            id="chunk-1",
            content_id="section-1",
            name="Section 1",
            content="Chunk content",
            metadata={"client_id": "tenant-1"},
            content_hash="hash-1",
        )
    ]

    documents = _to_agno_documents(chunks)

    assert len(documents) == 1
    assert documents[0].id == "chunk-1"
    assert documents[0].name == "Section 1"
    assert documents[0].content == "Chunk content"
    assert documents[0].meta_data == {"client_id": "tenant-1"}


def test_delete_vector_rows_for_client_prefers_vector_db_api() -> None:
    calls: list[dict] = []

    class FakeVectorDb:
        def delete_by_metadata(self, metadata: dict) -> None:
            calls.append(metadata)

    class FakeSession:
        def execute(self, *_args, **_kwargs) -> None:
            raise AssertionError("Raw SQL fallback should not be used when delete_by_metadata exists")

    _delete_vector_rows_for_client(FakeSession(), "tenant-1", FakeVectorDb())

    assert calls == [{"client_id": "tenant-1"}]


def test_delete_vector_rows_for_client_falls_back_to_sql() -> None:
    calls: list[tuple] = []

    class FakeSession:
        def execute(self, statement, params) -> None:
            calls.append((str(statement), params))

    class LegacyVectorDb:
        pass

    _delete_vector_rows_for_client(FakeSession(), "tenant-1", LegacyVectorDb())

    assert len(calls) == 1
    assert "DELETE FROM ai.agentic_customer_zoning_chunks" in calls[0][0]
    assert calls[0][1] == {"metadata": '{"client_id": "tenant-1"}'}


def test_upsert_vector_documents_passes_supported_kwargs() -> None:
    calls: list[dict] = []

    class FakeVectorDb:
        def upsert(self, *, content_hash: str, documents: list, filters: dict) -> None:
            calls.append(
                {
                    "content_hash": content_hash,
                    "documents": documents,
                    "filters": filters,
                }
            )

    documents = ["doc-1"]

    _upsert_vector_documents(
        FakeVectorDb(),
        documents=documents,
        client_id="tenant-1",
        content_hash="tenant-1:run-1",
    )

    assert calls == [
        {
            "content_hash": "tenant-1:run-1",
            "documents": documents,
            "filters": {"client_id": "tenant-1"},
        }
    ]


def test_upsert_vector_documents_drops_unsupported_kwargs() -> None:
    calls: list[list] = []

    class LegacyVectorDb:
        def upsert(self, *, documents: list) -> None:
            calls.append(documents)

    documents = ["doc-1"]

    _upsert_vector_documents(
        LegacyVectorDb(),
        documents=documents,
        client_id="tenant-1",
        content_hash="tenant-1:run-1",
    )

    assert calls == [documents]


def test_upsert_vector_documents_prefers_async_upsert() -> None:
    calls: list[dict] = []

    class FakeVectorDb:
        async def async_upsert(self, *, content_hash: str, documents: list, filters: dict) -> None:
            calls.append(
                {
                    "content_hash": content_hash,
                    "documents": documents,
                    "filters": filters,
                }
            )

        def upsert(self, **_kwargs) -> None:
            raise AssertionError("sync upsert should not be used when async_upsert exists")

    documents = ["doc-1"]

    _upsert_vector_documents(
        FakeVectorDb(),
        documents=documents,
        client_id="tenant-1",
        content_hash="tenant-1:run-1",
    )

    assert calls == [
        {
            "content_hash": "tenant-1:run-1",
            "documents": documents,
            "filters": {"client_id": "tenant-1"},
        }
    ]


def test_get_document_record_handles_missing_content_id() -> None:
    class DummyVectorDb(CustomerZoningPgVectorMixin):
        def __init__(self) -> None:
            self.document_embedder = object()
            self.table = types.SimpleNamespace(
                c={
                    "id": object(),
                    "name": object(),
                    "meta_data": object(),
                    "filters": object(),
                    "content": object(),
                    "embedding": object(),
                    "usage": object(),
                    "content_hash": object(),
                }
            )

        @staticmethod
        def _clean_content(content: str) -> str:
            return content.strip()

    class LegacyDocument:
        def __init__(self) -> None:
            self.id = "doc-1"
            self.name = "Doc 1"
            self.content = "  content  "
            self.meta_data = {"client_id": "tenant-1"}
            self.embedding = [0.1, 0.2]
            self.usage = {"tokens": 1}

        def embed(self, *, embedder) -> None:
            assert embedder is not None

    vector_db = DummyVectorDb()
    record = vector_db._get_document_record(
        LegacyDocument(),
        filters={"scope": "tenant"},
        content_hash="hash-1",
    )

    assert record["id"]
    assert record["name"] == "Doc 1"
    assert record["content"] == "content"
    assert record["content_hash"] == "hash-1"
    assert "content_id" not in record
    assert record["meta_data"] == {"client_id": "tenant-1", "scope": "tenant"}


def test_build_vector_db_filters_unsupported_pgvector_kwargs(monkeypatch) -> None:
    captured = {}

    class FakePgVector:
        def __init__(self, *, table_name, schema, db_url, embedder, search_type):
            captured.update(
                {
                    "table_name": table_name,
                    "schema": schema,
                    "db_url": db_url,
                    "embedder": embedder,
                    "search_type": search_type,
                }
            )

    fake_pgvector_module = types.ModuleType("agno.vectordb.pgvector")
    fake_pgvector_module.PgVector = FakePgVector

    fake_search_module = types.ModuleType("agno.vectordb.search")
    fake_search_module.SearchType = types.SimpleNamespace(hybrid="hybrid")

    monkeypatch.setitem(sys.modules, "agno.vectordb.pgvector", fake_pgvector_module)
    monkeypatch.setitem(sys.modules, "agno.vectordb.search", fake_search_module)
    monkeypatch.setattr("app.services.zoning_knowledge_service._build_embedder_pair", lambda: ("query", "document"))
    monkeypatch.setattr("app.services.zoning_knowledge_service.settings.database_url", "postgresql://test")

    vector_db = _build_vector_db()

    assert isinstance(vector_db, FakePgVector)
    assert captured["table_name"] == "agentic_customer_zoning_chunks"
    assert captured["schema"] == "ai"
    assert captured["db_url"] == "postgresql://test"
    assert captured["embedder"] == "query"
    assert captured["search_type"] == "hybrid"


def test_validate_crawl_output_rejects_empty_crawl() -> None:
    try:
        _validate_crawl_output("https://codehub.gridics.com/us/fl/miami", [], [])
    except RuntimeError as exc:
        assert "No static zoning-code pages were extracted" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for empty crawl output")


def test_is_codehub_source_and_alias_normalization() -> None:
    assert _is_codehub_source("https://codehub.gridics.com/us/fl/miami")
    assert not _is_codehub_source("https://example.com/us/fl/miami")
    assert _normalize_codehub_alias("https://codehub.gridics.com/us/fl/miami/") == "/us/fl/miami"


def test_extract_codehub_bootstrap_settings_reads_drupal_json() -> None:
    html = """
    <html><body>
    <script type="application/json" data-drupal-selector="drupal-settings-json">
    {"pageData":{"id":"45","fieldZoneiqTitle":"Miami 21 Code"}}
    </script>
    </body></html>
    """

    settings = _extract_codehub_bootstrap_settings(html)

    assert settings is not None
    assert settings["pageData"]["fieldZoneiqTitle"] == "Miami 21 Code"


def test_extract_codehub_page_content_builds_sections_from_dynamic_items() -> None:
    items = [
        {
            "id": "article-1",
            "docId": "45",
            "path": "/article-1",
            "ref": {"name": "section"},
            "li_attr": {"tag": "h2", "dataTag": "section", "hasChildren": 2},
            "text": "ARTICLE 1. DEFINITIONS",
        },
        {
            "id": "section-1",
            "docId": "45",
            "path": "/article-1/section-1",
            "ref": {"name": "subsection", "parent": "article-1"},
            "li_attr": {"tag": "h3", "dataTag": "subsection", "hasChildren": 1},
            "text": "1.1 DEFINITIONS OF TERMS",
        },
        {
            "id": "body-1",
            "docId": "45",
            "path": "/article-1/section-1/body-1",
            "ref": {"name": "subsection", "parent": "section-1"},
            "li_attr": {"dataTag": "BodyM", "hasChildren": 0},
            "text": "<p><strong>Abutting:</strong> To reach or touch.</p><p><strong>Accessory Use:</strong> A use incidental to another.</p>",
        },
        {
            "id": "section-2",
            "docId": "45",
            "path": "/article-1/section-2",
            "ref": {"name": "subsection", "parent": "article-1"},
            "li_attr": {"tag": "h3", "dataTag": "subsection", "hasChildren": 1},
            "text": "1.2 DEFINITIONS OF SIGNS",
        },
        {
            "id": "body-2",
            "docId": "45",
            "path": "/article-1/section-2/body-2",
            "ref": {"name": "subsection", "parent": "section-2"},
            "li_attr": {"dataTag": "BodyM", "hasChildren": 0},
            "text": "<p>Advertising Sign means any sign bearing advertising matter.</p>",
        },
    ]

    page = extract_codehub_page_content(
        "https://codehub.gridics.com/us/fl/miami",
        alias="/us/fl/miami",
        source_title="Miami 21 Code",
        status_code=200,
        items=items,
    )

    assert page.title == "Miami 21 Code"
    assert page.path == "/us/fl/miami"
    assert len(page.sections) == 2
    assert page.sections[0].title == "1.1 DEFINITIONS OF TERMS"
    assert page.sections[0].path == "ARTICLE 1. DEFINITIONS > 1.1 DEFINITIONS OF TERMS"
    assert "Abutting:" in page.sections[0].content
    assert page.sections[0].metadata["source_system"] == "codehub"
    assert page.sections[1].title == "1.2 DEFINITIONS OF SIGNS"
    assert "Advertising Sign" in page.text


def test_build_embedder_pair_rejects_non_positive_dimensions(monkeypatch) -> None:
    monkeypatch.setattr("app.services.zoning_knowledge_service.settings.zoning_embedder_dimensions", 0)

    try:
        _build_embedder_pair()
    except ValueError as exc:
        assert "greater than zero" in str(exc)
    else:
        raise AssertionError("expected ValueError for invalid dimensions")


def test_rate_limited_embedder_spaces_requests(monkeypatch) -> None:
    sleep_calls: list[float] = []

    class DummyEmbedder:
        def get_embedding_and_usage(self, text: str):
            return [1.0], {"text": text}

    clock = {"now": 0.0}

    def fake_monotonic() -> float:
        return clock["now"]

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr("app.services.zoning_knowledge_service.time.monotonic", fake_monotonic)
    monkeypatch.setattr("app.services.zoning_knowledge_service.time.sleep", fake_sleep)

    embedder = RateLimitedEmbedder(DummyEmbedder(), requests_per_minute=30, key="test:model")

    embedder.get_embedding_and_usage("first")
    embedder.get_embedding_and_usage("second")

    assert sleep_calls == [2.0]
