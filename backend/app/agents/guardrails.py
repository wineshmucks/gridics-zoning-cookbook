"""Domain guardrails for the zoning assistant."""

from __future__ import annotations

import re

from app.schemas.chat_request import GuardrailResult

_IN_SCOPE_PATTERNS = [
    r"\bt[1-6]\b",
    r"\bzoning\b",
    r"\boverlay\b",
    r"\bsetback",
    r"\bparking\b",
    r"\bheight\b",
    r"\bfar\b",
    r"\bdensity\b",
    r"\badu\b",
    r"\bpermitted use",
    r"\bmixed use\b",
    r"\bwhat can i build\b",
    r"\bhow many units\b",
    r"\bdevelopment code\b",
]

_OUT_OF_SCOPE_PATTERNS = [
    r"\bmayor\b",
    r"\bschool district\b",
    r"\brestaurant\b",
    r"\bmarketing copy\b",
    r"\bmortgage\b",
    r"\bnovel\b",
    r"\bweather\b",
    r"\bstock\b",
]


def evaluate_zoning_scope(question: str) -> GuardrailResult:
    """Classify whether a user question is within zoning scope."""

    normalized = (question or "").strip().lower()
    if not normalized:
        return GuardrailResult(
            in_scope=False,
            reason="The request is empty.",
            confidence=1.0,
            category="non_zoning",
        )

    in_scope_hits = sum(1 for pattern in _IN_SCOPE_PATTERNS if re.search(pattern, normalized))
    out_of_scope_hits = sum(1 for pattern in _OUT_OF_SCOPE_PATTERNS if re.search(pattern, normalized))

    if out_of_scope_hits and not in_scope_hits:
        return GuardrailResult(
            in_scope=False,
            reason="The request appears unrelated to zoning or land use regulation.",
            confidence=0.95,
            category="non_zoning",
        )

    if in_scope_hits:
        return GuardrailResult(
            in_scope=True,
            reason="The request falls within zoning or land use scope.",
            confidence=min(0.7 + 0.08 * in_scope_hits, 0.98),
            category="zoning",
        )

    plausible = any(keyword in normalized for keyword in ["build", "property", "parcel", "lot", "allowed", "here"])
    if plausible:
        return GuardrailResult(
            in_scope=True,
            reason="The request may be zoning-related, so it is being allowed through conservatively.",
            confidence=0.55,
            category="uncertain",
        )

    return GuardrailResult(
        in_scope=False,
        reason="The request does not appear to ask about zoning, land use, or development standards.",
        confidence=0.8,
        category="non_zoning",
    )
