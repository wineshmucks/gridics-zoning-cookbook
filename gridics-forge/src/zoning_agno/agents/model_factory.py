from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
import logging

from agno.models.openai import OpenAIChat
from agno.models.google import Gemini
from agno.models.groq import Groq
from agno.models.openrouter import OpenRouter

from zoning_agno.config import Settings


class ModelProvider(str, Enum):
    OPENAI = "openai"
    GROQ = "groq"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"


class TaskSize(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class TaskProfile(str, Enum):
    TEAM_COORDINATOR = "team_coordinator"
    INTAKE = "intake"
    DISTRICT_EXTRACTION = "district_extraction"
    USE_EXTRACTION = "use_extraction"
    DIMENSIONAL_EXTRACTION = "dimensional_extraction"
    PARKING_EXTRACTION = "parking_extraction"
    OVERLAY_EXTRACTION = "overlay_extraction"
    QA_REVIEW = "qa_review"


@dataclass(frozen=True)
class ModelSpec:
    provider: ModelProvider
    model_id: str
    temperature: float | None = None
    max_tokens: int | None = None
    extra: dict[str, Any] | None = None


class ModelFactory:
    """Centralized model selection for Agno agents and teams.

    The factory lets you map small/medium/large task sizes to different providers
    and model ids, while also supporting task-specific overrides.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._logger = logging.getLogger(__name__)

    def create_for_profile(self, profile: TaskProfile):
        spec = self._resolve_spec(profile)
        return self._build_model(spec, label=profile.value)

    def create_for_size(self, size: TaskSize):
        spec = self._spec_from_size(size)
        return self._build_model(spec, label=size.value)

    def _resolve_spec(self, profile: TaskProfile) -> ModelSpec:
        profile_size = {
            TaskProfile.TEAM_COORDINATOR: TaskSize.LARGE,
            TaskProfile.INTAKE: TaskSize.MEDIUM,
            TaskProfile.DISTRICT_EXTRACTION: TaskSize.MEDIUM,
            TaskProfile.USE_EXTRACTION: TaskSize.LARGE,
            TaskProfile.DIMENSIONAL_EXTRACTION: TaskSize.MEDIUM,
            TaskProfile.PARKING_EXTRACTION: TaskSize.SMALL,
            TaskProfile.OVERLAY_EXTRACTION: TaskSize.LARGE,
            TaskProfile.QA_REVIEW: TaskSize.LARGE,
        }[profile]

        task_override = self._task_override(profile)
        return task_override or self._spec_from_size(profile_size)

    def _task_override(self, profile: TaskProfile) -> ModelSpec | None:
        provider_name = getattr(self.settings, f"{profile.value}_provider", None)
        model_id = getattr(self.settings, f"{profile.value}_model_id", None)
        if not provider_name or not model_id:
            return None
        temperature = getattr(self.settings, f"{profile.value}_temperature", None)
        max_tokens = getattr(self.settings, f"{profile.value}_max_tokens", None)
        return ModelSpec(
            provider=ModelProvider(provider_name),
            model_id=model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            extra=self._provider_extra(ModelProvider(provider_name), profile),
        )

    def _spec_from_size(self, size: TaskSize) -> ModelSpec:
        provider = ModelProvider(getattr(self.settings, f"{size.value}_model_provider"))
        model_id = getattr(self.settings, f"{size.value}_model_id")
        temperature = getattr(self.settings, f"{size.value}_temperature")
        max_tokens = getattr(self.settings, f"{size.value}_max_tokens")
        return ModelSpec(
            provider=provider,
            model_id=model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            extra=self._provider_extra(provider, size),
        )

    def _provider_extra(self, provider: ModelProvider, profile_or_size: TaskProfile | TaskSize) -> dict[str, Any]:
        # Gemini supports native thinking controls that can be useful for
        # larger legal-reasoning tasks.
        # if provider == ModelProvider.GEMINI and profile_or_size in {
        #     TaskProfile.USE_EXTRACTION,
        #     TaskProfile.OVERLAY_EXTRACTION,
        #     TaskProfile.QA_REVIEW,
        #     TaskProfile.TEAM_COORDINATOR,
        #     TaskSize.LARGE,
        # }:
            # return {"thinking_enabled": True}
        return {}

    def _build_model(self, spec: ModelSpec, label: str | None = None):
        self._logger.warning(
            "Resolved model for %s -> provider=%s, model_id=%s",
            label or "unknown",
            spec.provider.value,
            spec.model_id,
        )
        kwargs: dict[str, Any] = {
            "name": f"{spec.provider.value}:{label}:{spec.model_id}" if label else f"{spec.provider.value}:{spec.model_id}",
            "id": spec.model_id,
            "temperature": spec.temperature,
            # "max_tokens": spec.max_tokens,
            "retries": self.settings.model_retries,
            "delay_between_retries": self.settings.model_retry_delay_seconds,
            "exponential_backoff": self.settings.model_retry_exponential_backoff,
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        if spec.extra:
            kwargs.update(spec.extra)

        if spec.provider == ModelProvider.GROQ:
            return Groq(**kwargs)
        if spec.provider == ModelProvider.OPENAI:
            return OpenAIChat(**kwargs)
        if spec.provider == ModelProvider.GEMINI:
            return Gemini(**kwargs)
        if spec.provider == ModelProvider.OPENROUTER:
            return OpenRouter(**kwargs)
        raise ValueError(f"Unsupported provider: {spec.provider}")
