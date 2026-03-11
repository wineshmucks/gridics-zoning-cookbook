"""Runtime configuration for AgentOS."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


def _load_env_files() -> None:
    if load_dotenv is None:
        return

    current = Path(__file__).resolve()
    package_dir = current.parent  # .../gridics-zoning-cookbook/agent_os
    repo_root = package_dir.parent  # .../gridics-zoning-cookbook

    # Prefer package-local env, then allow repo-level fallback.
    load_dotenv(package_dir / ".env", override=False)
    load_dotenv(repo_root / ".env", override=False)


_load_env_files()


RAW_MODEL = os.getenv("AGENT_OS_MODEL", "").strip()
if RAW_MODEL and ":" in RAW_MODEL:
    _provider, _model_id = RAW_MODEL.split(":", 1)
else:
    _provider, _model_id = "", ""

MODEL_PROVIDER = (
    os.getenv("AGENT_OS_MODEL_PROVIDER", "").strip().lower() or _provider.lower() or "cerebras"
)
MODEL_ID = os.getenv("AGENT_OS_MODEL_ID", "").strip() or _model_id or "llama-4-scout-17b-16e-instruct"
MODEL_TEMPERATURE = float(os.getenv("AGENT_OS_MODEL_TEMPERATURE", "0.0"))
GRIDICS_BASE_URL = os.getenv("GRIDICS_BASE_URL", "https://api.gridics.com/v1")
GRIDICS_TIMEOUT_SECONDS = int(os.getenv("GRIDICS_TIMEOUT_SECONDS", "20"))
AGENT_OS_HOST = os.getenv("AGENT_OS_HOST", "0.0.0.0")
AGENT_OS_PORT = int(os.getenv("AGENT_OS_PORT", "7777"))
AGENT_OS_INCLUDE_TOOL_TRACE_DETAILS = os.getenv(
    "AGENT_OS_INCLUDE_TOOL_TRACE_DETAILS", "false"
).strip().lower() in {"1", "true", "yes", "on"}


def get_gridics_api_key() -> str:
    key = os.getenv("GRIDICS_API_KEY", "").strip() or os.getenv("GRIDICS_CONSUMER_KEY", "").strip()
    if not key:
        raise ValueError("Set GRIDICS_API_KEY (or GRIDICS_CONSUMER_KEY)")
    return key


def build_agent_model():
    provider = MODEL_PROVIDER
    model_id = MODEL_ID
    temperature = MODEL_TEMPERATURE

    if provider == "cerebras":
        if not os.getenv("CEREBRAS_API_KEY", "").strip():
            raise ValueError("Set CEREBRAS_API_KEY for Cerebras models.")
        from agno.models.cerebras import Cerebras

        return Cerebras(id=model_id, temperature=temperature)

    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY", "").strip():
            raise ValueError("Set OPENAI_API_KEY for OpenAI models.")
        from agno.models.openai import OpenAIChat

        return OpenAIChat(id=model_id, temperature=temperature)

    if provider == "openrouter":
        if not os.getenv("OPENROUTER_API_KEY", "").strip():
            raise ValueError("Set OPENROUTER_API_KEY for OpenRouter models.")
        try:
            from agno.models.openrouter import OpenRouter
        except ImportError as e:
            raise ValueError("OpenRouter support requires Agno OpenRouter model support.") from e

        return OpenRouter(
            id=model_id,
            temperature=temperature,
            api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        )

    if provider == "gemini":
        if not os.getenv("GOOGLE_API_KEY", "").strip():
            raise ValueError("Set GOOGLE_API_KEY for Gemini models.")
        try:
            from agno.models.google import Gemini
        except ImportError as e:
            raise ValueError(
                "Gemini support requires `google-genai`. Install dependencies from requirements.txt."
            ) from e

        return Gemini(id=model_id, temperature=temperature)

    if provider == "groq":
        if not os.getenv("GROQ_API_KEY", "").strip():
            raise ValueError("Set GROQ_API_KEY for Groq models.")
        try:
            from agno.models.groq import Groq
        except ImportError as e:
            raise ValueError(
                "Groq support requires `groq`. Install dependencies from requirements.txt."
            ) from e

        return Groq(id=model_id, temperature=temperature)

    raise ValueError(
        f"Unsupported AGENT_OS_MODEL_PROVIDER '{provider}'. "
        "Supported providers: cerebras, openai, openrouter, gemini, groq."
    )
