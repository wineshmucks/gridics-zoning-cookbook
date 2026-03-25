from types import SimpleNamespace

from zoning_agno.config.settings import Settings
from zoning_agno.retrieval.embedder import DeterministicEmbedder, OpenRouterEmbedder, build_embedder


def test_deterministic_embedder_is_stable() -> None:
    embedder = DeterministicEmbedder(dimensions=8)
    left = embedder.embed_texts(["Minimum lot area is 5000 sf."])[0]
    right = embedder.embed_texts(["Minimum lot area is 5000 sf."])[0]
    other = embedder.embed_texts(["Parking is one space per unit."])[0]

    assert left == right
    assert left != other
    assert len(left) == 8


def test_build_embedder_returns_openrouter_embedder() -> None:
    settings = Settings(
        embedding_provider="openrouter",
        embedding_model="nvidia/llama-nemotron-embed-vl-1b-v2:free",
        embedding_dimensions=2048,
        embedding_api_key="test-key",
        embedding_base_url="https://openrouter.ai/api/v1",
    )
    embedder = build_embedder(settings)
    assert isinstance(embedder, OpenRouterEmbedder)


def test_openrouter_embedder_uses_openai_compatible_client(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeEmbeddings:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])

    class FakeClient:
        def __init__(self, **kwargs):
            calls.append({"client_kwargs": kwargs})
            self.embeddings = FakeEmbeddings()

    monkeypatch.setattr("zoning_agno.retrieval.embedder.OpenAI", FakeClient)
    embedder = OpenRouterEmbedder(
        model_name="nvidia/llama-nemotron-embed-vl-1b-v2:free",
        dimensions=2048,
        api_key="test-key",
    )
    result = embedder.embed_texts(["hello world"])

    assert result == [[0.1, 0.2, 0.3]]
    assert calls[0]["client_kwargs"]["api_key"] == "test-key"
    assert calls[0]["client_kwargs"]["base_url"] == "https://openrouter.ai/api/v1"
    assert calls[1]["model"] == "nvidia/llama-nemotron-embed-vl-1b-v2:free"
