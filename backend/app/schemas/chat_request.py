"""Request, guardrail, and response schemas for zoning chat orchestration."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    jurisdiction_id: str
    jurisdiction_name: str
    question: str
    property_selected: bool = False
    property_address: str | None = None
    property_lat: float | None = None
    property_lng: float | None = None


class GuardrailResult(BaseModel):
    in_scope: bool
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    category: Literal["zoning", "non_zoning", "uncertain"]
