"""Agno-friendly property context lookup tool."""

from __future__ import annotations

from typing import Any

from app.schemas.property_context import PropertyContextResult
from app.services.property_context_service import GridicsPropertyContextService


def get_property_context(
    lat: float,
    lng: float,
    jurisdiction_id: str,
    address: str | None = None,
    service: GridicsPropertyContextService | None = None,
) -> dict[str, Any]:
    """Return normalized property context for the given map coordinates."""

    resolver = service or GridicsPropertyContextService()
    result: PropertyContextResult = resolver.get_property_context(
        lat=lat,
        lng=lng,
        jurisdiction_id=jurisdiction_id,
        address=address,
    )
    return result.model_dump(mode="json")

