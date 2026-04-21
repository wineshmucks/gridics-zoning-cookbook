"""Normalized property context models for Gridics parcel lookups."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.citations import Citation


PropertyLookupStatus = Literal["success", "partial", "not_found", "unavailable"]


class PropertyContextFact(BaseModel):
    """A compact property fact safe to inject into the model context."""

    label: str
    value: str


class PropertyContextResult(BaseModel):
    """Stable internal schema for property-specific lookup results."""

    status: PropertyLookupStatus = "unavailable"
    jurisdiction_id: str
    jurisdiction_name: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    parcel_id: str | None = None
    zoning_district: str | None = None
    future_land_use: str | None = None
    overlays: list[str] = Field(default_factory=list)
    lot_area_sqft: float | None = None
    lot_area_acres: float | None = None
    frontage_ft: float | None = None
    dimensions: dict[str, float | None] = Field(default_factory=dict)
    allowed_uses: list[str] = Field(default_factory=list)
    setbacks_ft: dict[str, float | None] = Field(default_factory=dict)
    max_height_ft: float | None = None
    max_height_stories: float | None = None
    max_far: float | None = None
    max_density_units: float | None = None
    raw_response: dict = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    facts_for_prompt: list[PropertyContextFact] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    error_message: str | None = None
