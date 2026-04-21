"""Compatibility helpers for constructing Agno agents and models across minor versions."""

from __future__ import annotations

import os
from typing import Any

from agno.agent import Agent

from app.core.config import settings
from app.services.compat import build_with_supported_kwargs


def create_agent(**kwargs: Any) -> Agent:
    """Construct an Agent, omitting unsupported keyword args for older Agno builds."""
    # If the model attached to the agent is a Gemini model, avoid passing the
    # `tool_choice` string through to the underlying provider client because
    # different provider libraries expect different enum/enum-like types and
    # sending the raw legacy string can trigger validation errors (Gemini).
    tool_choice = kwargs.get("tool_choice")
    model = kwargs.get("model")
    try:
        provider = getattr(model, "_uzone_model_provider", None)
    except Exception:
        provider = None
    if isinstance(tool_choice, str) and provider == "gemini":
        # Remove the key so the provider client constructs its own function
        # calling config rather than receiving an invalid literal string.
        kwargs.pop("tool_choice", None)

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

    return os.getenv("GOOGLE_API_KEY"), "env_provider"


def build_agent_model(
    *,
    provider: str | None = None,
    model_id: str | None = None,
    model_id_override: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    allow_env_fallback: bool = True,
    allow_missing_api_key: bool = False,
):
    """Construct the Agno chat model configured for zoning chat agents."""

    if provider is not None and provider.strip().lower() != "gemini":
        raise RuntimeError("Assistant models are Gemini-only now.")

    active_model_id = (model_id_override or model_id or settings.zoning_agent_llm_model_id).strip()

    api_key, api_key_source = _get_agent_model_api_key(
        explicit_api_key=api_key,
        allow_env_fallback=allow_env_fallback,
    )
    if not api_key and allow_missing_api_key:
        api_key = "__tenant_api_key_required__"
        api_key_source = "missing"

    if not active_model_id:
        raise RuntimeError("Model ID must be specified for Gemini assistant models.")

    def missing_key_error(env_name: str) -> RuntimeError:
        if allow_env_fallback:
            return RuntimeError(f"Set {env_name} for the Gemini zoning agent.")
        return RuntimeError(
            "Missing API key for the Gemini zoning agent. "
            "Save the provider key in super-admin assistant setup."
        )

    if not api_key and not allow_missing_api_key:
        raise missing_key_error("GOOGLE_API_KEY")

    from agno.models.google import Gemini
    return _attach_model_trace(
        build_with_supported_kwargs(Gemini, id=active_model_id, api_key=api_key),
        provider="gemini",
        model_id=active_model_id,
        api_key_source=api_key_source,
        api_key=api_key,
    )
