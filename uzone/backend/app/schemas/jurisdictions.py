"""Jurisdiction API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class JurisdictionCreate(BaseModel):
    code: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    department_name: str = Field(min_length=1, max_length=255)
    public_site_title: str | None = Field(default=None, max_length=255)
    public_contact_email: EmailStr | None = None
    public_contact_phone: str | None = Field(default=None, max_length=50)
    timezone: str = Field(default="UTC", min_length=1, max_length=100)
    is_active: bool = True
    settings_json: dict | None = None


class JurisdictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    department_name: str
    public_site_title: str | None
    public_contact_email: EmailStr | None
    public_contact_phone: str | None
    timezone: str
    is_active: bool
    settings_json: dict | None
    created_at: datetime
    updated_at: datetime

