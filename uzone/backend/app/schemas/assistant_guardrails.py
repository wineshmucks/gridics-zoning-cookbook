"""Assistant turn contract schemas for policy and routing guardrails."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


IntentType = Literal["specific_address", "general_zoning", "out_of_scope"]
JurisdictionStatus = Literal["in_jurisdiction", "out_of_jurisdiction", "unresolved", "not_applicable"]
PolicyAction = Literal["allow", "deny", "clarify"]
ClarificationType = Literal[
    "none",
    "scope",
    "address_missing_details",
    "address_ambiguous",
    "jurisdiction_mismatch",
]


class PolicyDecisionRead(BaseModel):
    decision: PolicyAction
    reason_code: str
    reason: str


class AssistantTurnContract(BaseModel):
    intent_type: IntentType
    jurisdiction_status: JurisdictionStatus
    needs_clarification: bool
    clarification_type: ClarificationType = "none"
    policy_decision: PolicyDecisionRead
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
