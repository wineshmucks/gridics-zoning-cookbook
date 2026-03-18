"""Minimal Clerk API helpers used by backend routes."""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

CLERK_API_BASE_URL = "https://api.clerk.com/v1"


def get_clerk_organization(organization_id: str | None) -> dict | None:
    normalized_organization_id = organization_id.strip() if organization_id else ""
    if not normalized_organization_id or not settings.clerk_secret_key:
        return None

    try:
        response = httpx.get(
            f"{CLERK_API_BASE_URL}/organizations/{normalized_organization_id}",
            headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            timeout=5.0,
        )
    except httpx.HTTPError:
        logger.exception("Unable to load Clerk organization %s.", normalized_organization_id)
        return None

    if response.status_code == 200:
        payload = response.json()
        return payload if isinstance(payload, dict) else None

    if response.status_code != 404:
        logger.warning(
            "Clerk organization fetch for %s returned status %s.",
            normalized_organization_id,
            response.status_code,
        )
    return None


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

    return get_clerk_organization(normalized_organization_id) is not None
