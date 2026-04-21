"""Typed citation and evidence schemas for grounded zoning answers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


CitationSourceType = Literal["gridics_property", "zoning_code", "user_context"]


class Citation(BaseModel):
    """A normalized citation that can be shown to users and reused by validators."""

    id: str = Field(min_length=1)
    source_type: CitationSourceType
    label: str = Field(min_length=1)
    excerpt: str | None = None
    section: str | None = None
    url: HttpUrl | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class EvidenceBundle(BaseModel):
    """Compact evidence passed into answer composition and validation."""

    citations: list[Citation] = Field(default_factory=list)
    property_context_summary: list[str] = Field(default_factory=list)
    knowledge_summary: list[str] = Field(default_factory=list)

