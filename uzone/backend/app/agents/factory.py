"""Compatibility helpers for constructing Agno agents and models across minor versions."""

from __future__ import annotations

import os
from typing import Any

from agno.agent import Agent

from app.core.config import settings
from app.services.compat import build_with_supported_kwargs


def create_agent(**kwargs: Any) -> Agent:
    """Construct an Agent, omitting unsupported keyword args for older Agno builds."""
    return build_with_supported_kwargs(Agent, **kwargs)


def _get_agent_model_api_key(provider: str) -> str | None:
    if settings.zoning_agent_llm_api_key:
        return settings.zoning_agent_llm_api_key

    if provider == "gemini":
        return os.getenv("GOOGLE_API_KEY")

    if provider == "openrouter":
        return os.getenv("OPENROUTER_API_KEY")

    if provider == "openai":
        return os.getenv("OPENAI_API_KEY")

    return None


def build_agent_model(*, model_id_override: str | None = None):
    """Construct the Agno chat model configured for zoning chat agents."""
    provider = settings.zoning_agent_llm_provider.strip().lower()
    model_id = model_id_override.strip() if isinstance(model_id_override, str) and model_id_override.strip() else settings.zoning_agent_llm_model_id.strip()
    api_key = _get_agent_model_api_key(provider)

    if not model_id:
        raise RuntimeError("Set UZONE_ZONING_AGENT_LLM_MODEL_ID for the zoning agent.")

    if provider == "gemini":
        if not api_key:
            raise RuntimeError(
                "Set UZONE_ZONING_AGENT_LLM_API_KEY or GOOGLE_API_KEY for the Gemini zoning agent."
            )
        from agno.models.google import Gemini

        return build_with_supported_kwargs(Gemini, id=model_id, api_key=api_key)

    if provider == "openrouter":
        if not api_key:
            raise RuntimeError(
                "Set UZONE_ZONING_AGENT_LLM_API_KEY or OPENROUTER_API_KEY for the OpenRouter zoning agent."
            )
        from agno.models.openrouter import OpenRouter

        return build_with_supported_kwargs(
            OpenRouter,
            id=model_id,
            api_key=api_key,
            base_url=settings.zoning_agent_llm_base_url or "https://openrouter.ai/api/v1",
        )

    if provider == "openai":
        if not api_key:
            raise RuntimeError("Set UZONE_ZONING_AGENT_LLM_API_KEY or OPENAI_API_KEY for the OpenAI zoning agent.")
        from agno.models.openai import OpenAIChat

        return build_with_supported_kwargs(
            OpenAIChat,
            id=model_id,
            api_key=api_key,
            base_url=settings.zoning_agent_llm_base_url,
        )

    raise RuntimeError(
        f"Unsupported zoning agent LLM provider '{settings.zoning_agent_llm_provider}'. "
        "Supported providers: gemini, openrouter, openai."
    )
