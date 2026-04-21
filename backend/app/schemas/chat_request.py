"""Request, guardrail, and response schemas for zoning chat orchestration."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.citations import Citation


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    jurisdiction_id: str
    jurisdiction_name: str
    question: str
    property_selected: bool = False
    property_address: str | None = None
    property_lat: float | None = None
    property_lng: float | None = None
    conversation_history: list[ConversationTurn] = Field(default_factory=list)


class GuardrailResult(BaseModel):
    in_scope: bool
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    category: Literal["zoning", "non_zoning", "uncertain"]


class AnswerDraft(BaseModel):
    direct_answer: str
    why: list[str] = Field(default_factory=list)
    property_context_used: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    cited_evidence_ids: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    follow_up_suggestion: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    used_property_context: bool = False
    grounding_status: str
    confidence: str
    follow_up_suggestion: str | None = None
    guardrail: GuardrailResult

