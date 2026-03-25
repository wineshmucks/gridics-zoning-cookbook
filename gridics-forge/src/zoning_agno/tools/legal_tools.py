from __future__ import annotations

from zoning_agno.models.schemas import Citation, ReviewFlag, ReviewSeverity


def build_cross_reference_index() -> dict[str, list[str]]:
    """Placeholder for a legal cross-reference graph."""
    return {}


def make_missing_evidence_flag(sheet_name: str, field_key: str, reason: str) -> ReviewFlag:
    return ReviewFlag(
        severity=ReviewSeverity.HIGH,
        sheet_name=sheet_name,
        field_key=field_key,
        issue_type="missing_evidence",
        reason=reason,
        suggested_action="Review source text and attach an authoritative citation before export.",
        citations=[Citation(quote=reason, confidence=0.0)],
    )
