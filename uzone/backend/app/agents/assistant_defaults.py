"""Shared assistant defaults used by runtime orchestration and admin UI."""

from __future__ import annotations

CUSTOMER_ZONING_ASSISTANT_TARGET_ID = "customer_zoning_team"
LEGACY_CUSTOMER_ZONING_ASSISTANT_TARGET_ID = "customer-zoning-agent"
PUBLIC_CUSTOMER_ZONING_ASSISTANT_TARGET_ID = "customer-zoning-team"

ASSISTANT_TARGET_IDS = (
    CUSTOMER_ZONING_ASSISTANT_TARGET_ID,
    "parcel-data-agent",
    "code-researcher-agent",
)

CODE_DEFAULT_ASSISTANT_MODEL_TARGETS: dict[str, dict[str, str | None]] = {
    CUSTOMER_ZONING_ASSISTANT_TARGET_ID: {
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

ASSISTANT_TARGET_ID_ALIASES = {
    LEGACY_CUSTOMER_ZONING_ASSISTANT_TARGET_ID: CUSTOMER_ZONING_ASSISTANT_TARGET_ID,
    PUBLIC_CUSTOMER_ZONING_ASSISTANT_TARGET_ID: CUSTOMER_ZONING_ASSISTANT_TARGET_ID,
}
