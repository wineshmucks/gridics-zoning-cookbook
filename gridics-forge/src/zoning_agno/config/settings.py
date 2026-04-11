from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TEMPLATE_PATH = "./Gridcs.xlsx" if (PROJECT_ROOT / "Gridcs.xlsx").exists() else "./data/templates/zoning_template.xlsx"
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _env_first(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    return default


def _float_env(name: str, default: str | None = None) -> float | None:
    value = _env_first(name, default=default)
    return float(value) if value not in (None, "") else None


def _int_env(name: str, default: str | None = None) -> int | None:
    value = _env_first(name, default=default)
    return int(value) if value not in (None, "") else None


class Settings(BaseModel):
    project_root: Path = Field(default=PROJECT_ROOT)

    model_retries: int = Field(default=int(os.getenv("MODEL_RETRIES", "2")))
    model_retry_delay_seconds: int = Field(default=int(os.getenv("MODEL_RETRY_DELAY_SECONDS", "1")))
    model_retry_exponential_backoff: bool = Field(
        default=os.getenv("MODEL_RETRY_EXPONENTIAL_BACKOFF", "true").lower() == "true"
    )

    small_model_provider: str = Field(default=os.getenv("SMALL_MODEL_PROVIDER", "groq"))
    small_model_id: str = Field(default=os.getenv("SMALL_MODEL_ID", "llama-3.1-8b-instant"))
    small_temperature: float | None = Field(default=_float_env("SMALL_TEMPERATURE", "0.0"))
    small_max_tokens: int | None = Field(default=_int_env("SMALL_MAX_TOKENS", "4096"))

    medium_model_provider: str = Field(default=os.getenv("MEDIUM_MODEL_PROVIDER", "gemini"))
    medium_model_id: str = Field(default=os.getenv("MEDIUM_MODEL_ID", "gemini-2.0-flash"))
    medium_temperature: float | None = Field(default=_float_env("MEDIUM_TEMPERATURE", "0.0"))
    medium_max_tokens: int | None = Field(default=_int_env("MEDIUM_MAX_TOKENS", "8192"))

    large_model_provider: str = Field(default=os.getenv("LARGE_MODEL_PROVIDER", "openrouter"))
    large_model_id: str = Field(default=os.getenv("LARGE_MODEL_ID", "google/gemini-2.5-pro"))
    large_temperature: float | None = Field(default=_float_env("LARGE_TEMPERATURE", "0.0"))
    large_max_tokens: int | None = Field(default=_int_env("LARGE_MAX_TOKENS", "16384"))

    team_coordinator_provider: str | None = Field(default=os.getenv("TEAM_COORDINATOR_PROVIDER"))
    team_coordinator_model_id: str | None = Field(default=os.getenv("TEAM_COORDINATOR_MODEL_ID"))
    team_coordinator_temperature: float | None = Field(default=_float_env("TEAM_COORDINATOR_TEMPERATURE"))
    team_coordinator_max_tokens: int | None = Field(default=_int_env("TEAM_COORDINATOR_MAX_TOKENS"))

    intake_provider: str | None = Field(default=os.getenv("INTAKE_PROVIDER"))
    intake_model_id: str | None = Field(default=os.getenv("INTAKE_MODEL_ID"))
    intake_temperature: float | None = Field(default=_float_env("INTAKE_TEMPERATURE"))
    intake_max_tokens: int | None = Field(default=_int_env("INTAKE_MAX_TOKENS"))

    district_extraction_provider: str | None = Field(default=os.getenv("DISTRICT_EXTRACTION_PROVIDER"))
    district_extraction_model_id: str | None = Field(default=os.getenv("DISTRICT_EXTRACTION_MODEL_ID"))
    district_extraction_temperature: float | None = Field(default=_float_env("DISTRICT_EXTRACTION_TEMPERATURE"))
    district_extraction_max_tokens: int | None = Field(default=_int_env("DISTRICT_EXTRACTION_MAX_TOKENS"))

    use_extraction_provider: str | None = Field(default=os.getenv("USE_EXTRACTION_PROVIDER"))
    use_extraction_model_id: str | None = Field(default=os.getenv("USE_EXTRACTION_MODEL_ID"))
    use_extraction_temperature: float | None = Field(default=_float_env("USE_EXTRACTION_TEMPERATURE"))
    use_extraction_max_tokens: int | None = Field(default=_int_env("USE_EXTRACTION_MAX_TOKENS"))

    dimensional_extraction_provider: str | None = Field(default=os.getenv("DIMENSIONAL_EXTRACTION_PROVIDER"))
    dimensional_extraction_model_id: str | None = Field(default=os.getenv("DIMENSIONAL_EXTRACTION_MODEL_ID"))
    dimensional_extraction_temperature: float | None = Field(default=_float_env("DIMENSIONAL_EXTRACTION_TEMPERATURE"))
    dimensional_extraction_max_tokens: int | None = Field(default=_int_env("DIMENSIONAL_EXTRACTION_MAX_TOKENS"))

    parking_extraction_provider: str | None = Field(default=os.getenv("PARKING_EXTRACTION_PROVIDER"))
    parking_extraction_model_id: str | None = Field(default=os.getenv("PARKING_EXTRACTION_MODEL_ID"))
    parking_extraction_temperature: float | None = Field(default=_float_env("PARKING_EXTRACTION_TEMPERATURE"))
    parking_extraction_max_tokens: int | None = Field(default=_int_env("PARKING_EXTRACTION_MAX_TOKENS"))

    overlay_extraction_provider: str | None = Field(default=os.getenv("OVERLAY_EXTRACTION_PROVIDER"))
    overlay_extraction_model_id: str | None = Field(default=os.getenv("OVERLAY_EXTRACTION_MODEL_ID"))
    overlay_extraction_temperature: float | None = Field(default=_float_env("OVERLAY_EXTRACTION_TEMPERATURE"))
    overlay_extraction_max_tokens: int | None = Field(default=_int_env("OVERLAY_EXTRACTION_MAX_TOKENS"))

    qa_review_provider: str | None = Field(default=os.getenv("QA_REVIEW_PROVIDER"))
    qa_review_model_id: str | None = Field(default=os.getenv("QA_REVIEW_MODEL_ID"))
    qa_review_temperature: float | None = Field(default=_float_env("QA_REVIEW_TEMPERATURE"))
    qa_review_max_tokens: int | None = Field(default=_int_env("QA_REVIEW_MAX_TOKENS"))

    workbook_template_path: Path = Field(
        default=Path(os.getenv("WORKBOOK_TEMPLATE_PATH", DEFAULT_TEMPLATE_PATH))
    )
    default_source_kind: str = Field(default=os.getenv("DEFAULT_SOURCE_KIND", "municode"))
    default_source_url: str | None = Field(default=os.getenv("DEFAULT_SOURCE_URL"))
    supplemental_source_urls: list[str] = Field(
        default_factory=lambda: [
            value.strip()
            for value in (
                os.getenv("SUPPLEMENTAL_SOURCE_URLS", "") or os.getenv("MUNICODE_SUPPLEMENTAL_SOURCE_URLS", "")
            ).split(",")
            if value.strip()
        ]
    )

    database_url: str = Field(
        default_factory=lambda: _env_first(
            "DATABASE_URL",
            default="postgresql+psycopg://postgres:postgres@localhost:5432/gridics_forge",
        )
        or "postgresql+psycopg://postgres:postgres@localhost:5432/gridics_forge"
    )
    database_echo: bool = Field(
        default_factory=lambda: (_env_first("DATABASE_ECHO", default="false") or "false").lower() == "true"
    )
    embedding_model: str = Field(
        default_factory=lambda: _env_first(
            "EMBEDDING_MODEL",
            default="text-embedding-3-large",
        )
        or "text-embedding-3-large"
    )
    embedding_provider: str = Field(
        default_factory=lambda: _env_first(
            "EMBEDDING_PROVIDER",
            default="openai",
        )
        or "openai"
    )
    embedding_dimensions: int = Field(
        default_factory=lambda: int(
            _env_first(
                "EMBEDDING_DIMENSIONS",
                default="3072",
            )
            or "3072"
        )
    )
    embedding_batch_size: int = Field(
        default_factory=lambda: int(_env_first("EMBEDDING_BATCH_SIZE", default="32") or "32")
    )
    embedding_api_key: str | None = Field(
        default_factory=lambda: _env_first(
            "EMBEDDING_API_KEY",
            "OPENROUTER_API_KEY",
            "OPENAI_API_KEY",
        )
    )
    embedding_base_url: str | None = Field(
        default_factory=lambda: _env_first("EMBEDDING_BASE_URL")
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
