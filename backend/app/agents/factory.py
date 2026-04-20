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


def _mask_api_key_suffix(api_key: str | None) -> str | None:
    if not api_key:
        return None
    suffix = api_key[-4:]
    return suffix if suffix else None


def _attach_model_trace(model: Any, *, provider: str, model_id: str, api_key_source: str, api_key: str | None) -> Any:
    setattr(model, "_uzone_model_provider", provider)
    setattr(model, "_uzone_model_id", model_id)
    setattr(model, "_uzone_api_key_source", api_key_source)
    setattr(model, "_uzone_api_key_suffix", _mask_api_key_suffix(api_key))
    return model


def get_model_trace(model: Any) -> dict[str, str | None]:
    return {
        "provider": getattr(model, "_uzone_model_provider", None),
        "model_id": getattr(model, "_uzone_model_id", None),
        "api_key_source": getattr(model, "_uzone_api_key_source", None),
        "api_key_suffix": getattr(model, "_uzone_api_key_suffix", None),
    }


def _get_agent_model_api_key(
    provider: str,
    *,
    explicit_api_key: str | None = None,
    allow_env_fallback: bool = False,
) -> tuple[str | None, str]:
    if explicit_api_key:
        return explicit_api_key, "tenant_db"

    if not allow_env_fallback:
        return None, "missing"

    if settings.zoning_agent_llm_api_key:
        return settings.zoning_agent_llm_api_key, "env_generic"

    if provider == "gemini":
        return os.getenv("GOOGLE_API_KEY"), "env_provider"

    return None, "missing"


def build_agent_model(
    *,
    provider: str | None = None,
    model_id: str | None = None,
    model_id_override: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    max_tokens: int = 4096,
    allow_env_fallback: bool = True,
    allow_missing_api_key: bool = False,
):
    """Construct the Agno chat model configured for zoning chat agents."""
    
    # 1. Determine actual provider and model (fallback to settings if None)
    active_provider = (provider or settings.zoning_agent_llm_provider).strip().lower()
    active_model_id = (model_id_override or model_id or settings.zoning_agent_llm_model_id).strip()
    
    # 2. Fetch the safe API key
    api_key, api_key_source = _get_agent_model_api_key(
        active_provider,
        explicit_api_key=api_key,
        allow_env_fallback=allow_env_fallback,
    )
    if not api_key and allow_missing_api_key:
        api_key = "__tenant_api_key_required__"
        api_key_source = "missing"

    if not active_model_id:
        raise RuntimeError(f"Model ID must be specified for provider '{active_provider}'.")

    def missing_key_error(provider_label: str, env_name: str) -> RuntimeError:
        if allow_env_fallback:
            return RuntimeError(f"Set {env_name} for the {provider_label} zoning agent.")
        return RuntimeError(
            f"Missing API key for tenant-configured provider '{active_provider}'. "
            "Save the provider key in super-admin assistant setup."
        )

    if active_provider != "gemini":
        raise RuntimeError(
            f"Unsupported zoning agent LLM provider '{active_provider}'. "
            "Supported providers: gemini."
        )

    if not api_key and not allow_missing_api_key:
        raise missing_key_error("Gemini", "GOOGLE_API_KEY")
    from agno.models.google import Gemini
    return _attach_model_trace(
        build_with_supported_kwargs(Gemini, id=active_model_id, api_key=api_key),
        provider=active_provider,
        model_id=active_model_id,
        api_key_source=api_key_source,
        api_key=api_key,
    )
