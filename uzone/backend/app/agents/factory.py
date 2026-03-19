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


def _get_agent_model_api_key(provider: str, is_override: bool = False, explicit_api_key: str | None = None) -> str | None:
    if explicit_api_key:
        return explicit_api_key

    # Only use the generic global key if we are NOT overriding the default provider
    if not is_override and settings.zoning_agent_llm_api_key:
        return settings.zoning_agent_llm_api_key

    if provider == "gemini":
        return os.getenv("GOOGLE_API_KEY")
    if provider == "openrouter":
        return os.getenv("OPENROUTER_API_KEY")
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY")
    if provider == "groq":
        return os.getenv("GROQ_API_KEY")

    return None


def build_agent_model(
    *,
    provider: str | None = None,
    model_id: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    max_tokens: int = 4096,
):
    """Construct the Agno chat model configured for zoning chat agents."""
    
    # 1. Determine actual provider and model (fallback to settings if None)
    active_provider = (provider or settings.zoning_agent_llm_provider).strip().lower()
    active_model_id = (model_id or settings.zoning_agent_llm_model_id).strip()
    
    # Check if we are diverging from the global default provider
    is_override = bool(provider and provider.strip().lower() != settings.zoning_agent_llm_provider.strip().lower())
    
    # 2. Fetch the safe API key
    api_key = _get_agent_model_api_key(active_provider, is_override=is_override, explicit_api_key=api_key)

    if not active_model_id:
        raise RuntimeError(f"Model ID must be specified for provider '{active_provider}'.")

    if active_provider == "gemini":
        if not api_key:
            raise RuntimeError("Set GOOGLE_API_KEY for the Gemini zoning agent.")
        from agno.models.google import Gemini
        return build_with_supported_kwargs(Gemini, id=active_model_id, api_key=api_key)

    if active_provider == "openrouter":
        if not api_key:
            raise RuntimeError("Set OPENROUTER_API_KEY for the OpenRouter zoning agent.")
        from agno.models.openrouter import OpenRouter
        return build_with_supported_kwargs(
            OpenRouter,
            id=active_model_id,
            api_key=api_key,
            base_url=base_url or settings.zoning_agent_llm_base_url or "https://openrouter.ai/api/v1",
            max_tokens=max_tokens,
        )

    if active_provider == "openai":
        if not api_key:
            raise RuntimeError("Set OPENAI_API_KEY for the OpenAI zoning agent.")
        from agno.models.openai import OpenAIChat
        return build_with_supported_kwargs(
            OpenAIChat,
            id=active_model_id,
            api_key=api_key,
            base_url=base_url or settings.zoning_agent_llm_base_url,
        )

    if active_provider == "groq":
        if not api_key:
            raise RuntimeError("Set GROQ_API_KEY for the Groq zoning agent.")
        from agno.models.groq import Groq
        return build_with_supported_kwargs(
            Groq,
            id=active_model_id,
            api_key=api_key,
        )

    raise RuntimeError(
        f"Unsupported zoning agent LLM provider '{active_provider}'. "
        "Supported providers: gemini, openrouter, openai, groq."
    )
