from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
import math

from openai import OpenAI

from zoning_agno.config import Settings


class BaseEmbedder(ABC):
    model_name: str

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input string."""


class DeterministicEmbedder(BaseEmbedder):
    """Small deterministic embedder for tests and local smoke runs."""

    def __init__(self, model_name: str = "deterministic-hash", dimensions: int = 32) -> None:
        self.model_name = model_name
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        counts = [0.0] * self.dimensions
        normalized = text.strip().lower() or "<empty>"
        for token in normalized.split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for idx in range(self.dimensions):
                counts[idx] += digest[idx % len(digest)] / 255.0
        norm = math.sqrt(sum(value * value for value in counts)) or 1.0
        return [value / norm for value in counts]


class OpenAIEmbedder(BaseEmbedder):
    def __init__(
        self,
        model_name: str,
        dimensions: int | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.dimensions = dimensions
        client_kwargs = {}
        if api_key:
            client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = OpenAI(**client_kwargs)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        kwargs = {"model": self.model_name, "input": texts, "encoding_format": "float"}
        if self.dimensions and self.model_name.startswith("text-embedding-3"):
            kwargs["dimensions"] = self.dimensions
        response = self._client.embeddings.create(**kwargs)
        return [list(item.embedding) for item in response.data]


class OpenRouterEmbedder(OpenAIEmbedder):
    def __init__(self, model_name: str, dimensions: int | None = None, *, api_key: str | None = None, base_url: str | None = None) -> None:
        super().__init__(
            model_name=model_name,
            dimensions=dimensions,
            api_key=api_key,
            base_url=base_url or "https://openrouter.ai/api/v1",
        )


def build_embedder(settings: Settings) -> BaseEmbedder:
    provider = settings.embedding_provider.lower().strip()
    if provider in {"deterministic", "dummy", "hash"}:
        return DeterministicEmbedder(
            model_name=settings.embedding_model,
            dimensions=min(settings.embedding_dimensions, 256),
        )
    if provider == "openai":
        return OpenAIEmbedder(
            model_name=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
        )
    if provider == "openrouter":
        return OpenRouterEmbedder(
            model_name=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
        )
    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")
