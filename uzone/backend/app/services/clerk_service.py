"""Minimal Clerk API helpers used by backend routes."""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

CLERK_API_BASE_URL = "https://api.clerk.com/v1"


def clerk_organization_exists(organization_id: str | None) -> bool:
    normalized_organization_id = organization_id.strip() if organization_id else ""
    if not normalized_organization_id:
        return False

    if not settings.clerk_secret_key:
        logger.warning(
            "Unable to validate Clerk organization %s because CLERK_SECRET_KEY is not configured.",
            normalized_organization_id,
        )
        return False

    try:
        response = httpx.get(
            f"{CLERK_API_BASE_URL}/organizations/{normalized_organization_id}",
            headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            timeout=5.0,
        )
    except httpx.HTTPError:
        logger.exception("Unable to validate Clerk organization %s.", normalized_organization_id)
        return False

    if response.status_code == 200:
        return True

    if response.status_code == 404:
        return False

    logger.warning(
        "Clerk organization lookup for %s returned status %s.",
        normalized_organization_id,
        response.status_code,
    )
    return False
