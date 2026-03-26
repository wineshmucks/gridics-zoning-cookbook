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


def update_clerk_organization(
    organization_id: str | None,
    *,
    name: str | None = None,
    slug: str | None = None,
    update_slug: bool = False,
) -> bool:
    normalized_organization_id = organization_id.strip() if organization_id else ""
    if not normalized_organization_id or not settings.clerk_secret_key:
        return False

    payload: dict[str, str | None] = {}
    if name is not None:
        normalized_name = name.strip()
        if normalized_name:
            payload["name"] = normalized_name

    if update_slug:
        normalized_slug = slug.strip() if slug else ""
        payload["slug"] = normalized_slug or None

    if not payload:
        return False

    try:
        response = httpx.patch(
            f"{CLERK_API_BASE_URL}/organizations/{normalized_organization_id}",
            headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            json=payload,
            timeout=5.0,
        )
    except httpx.HTTPError:
        logger.exception("Unable to update Clerk organization %s.", normalized_organization_id)
        return False

    if 200 <= response.status_code < 300:
        return True

    logger.warning(
        "Clerk organization update for %s returned status %s.",
        normalized_organization_id,
        response.status_code,
    )
    return False


def delete_clerk_organization(organization_id: str | None) -> bool:
    normalized_organization_id = organization_id.strip() if organization_id else ""
    if not normalized_organization_id or not settings.clerk_secret_key:
        return False

    try:
        response = httpx.delete(
            f"{CLERK_API_BASE_URL}/organizations/{normalized_organization_id}",
            headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            timeout=5.0,
        )
    except httpx.HTTPError:
        logger.exception("Unable to delete Clerk organization %s.", normalized_organization_id)
        return False

    if 200 <= response.status_code < 300 or response.status_code == 404:
        return True

    logger.warning(
        "Clerk organization delete for %s returned status %s.",
        normalized_organization_id,
        response.status_code,
    )
    return False


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
