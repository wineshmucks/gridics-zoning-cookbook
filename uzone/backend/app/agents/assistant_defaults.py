"""Shared assistant defaults used by runtime orchestration and admin UI."""

from __future__ import annotations

ASSISTANT_TARGET_IDS = (
    "customer-zoning-agent",
    "parcel-data-agent",
    "code-researcher-agent",
)

CODE_DEFAULT_ASSISTANT_MODEL_TARGETS: dict[str, dict[str, str | None]] = {
    "customer-zoning-agent": {
        "provider": "gemini",
        "model_id": "gemini-2.5-flash-lite",
        "base_url": None,
    },
    "parcel-data-agent": {
        "provider": "gemini",
        "model_id": "gemini-2.5-flash-lite",
        "base_url": None,
    },
    "code-researcher-agent": {
        "provider": "gemini",
        "model_id": "gemini-2.5-pro",
        "base_url": None,
    },
}

