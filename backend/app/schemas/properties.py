"""Property API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PropertyCreate(BaseModel):
    jurisdiction_id: str
    source_system: str = Field(min_length=1, max_length=100)
    source_property_id: str | None = Field(default=None, max_length=255)
    group_id: str | None = Field(default=None, max_length=255)
    apn: str | None = Field(default=None, max_length=255)
    address_line1: str = Field(min_length=1, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    latitude: float | None = None
    longitude: float | None = None


class PropertyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    jurisdiction_id: str
    source_system: str
    source_property_id: str | None
    group_id: str | None
    apn: str | None
    address_line1: str
    address_line2: str | None
    city: str
    state: str
    postal_code: str | None
    latitude: float | None
    longitude: float | None
    created_at: datetime
    updated_at: datetime


class PropertySnapshotCreate(BaseModel):
    property_id: str
    captured_by_user_id: str | None = None
    capture_reason: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=1, max_length=255)
    apn: str | None = Field(default=None, max_length=255)
    group_id: str | None = Field(default=None, max_length=255)
    zoning_code: str | None = Field(default=None, max_length=100)
    zoning_name: str | None = Field(default=None, max_length=255)
    lot_size_sf: int | None = Field(default=None, ge=0)
    permitted_uses_json: dict | list | None = None
    restrictions_json: dict | list | None = None
    overlays_json: dict | list | None = None
    raw_source_payload_json: dict | list | None = None
    source_payload_hash: str | None = Field(default=None, max_length=64)


class PropertySnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    property_id: str
    captured_by_user_id: str | None
    capture_reason: str
    address: str
    apn: str | None
    group_id: str | None
    zoning_code: str | None
    zoning_name: str | None
    lot_size_sf: int | None
    permitted_uses_json: dict | list | None
    restrictions_json: dict | list | None
    overlays_json: dict | list | None
    raw_source_payload_json: dict | list | None
    source_payload_hash: str | None
    captured_at: datetime
    created_at: datetime
