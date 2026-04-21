"""Grounding and citation validation for zoning assistant responses."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.chat_request import AnswerDraft, ChatResponse, GuardrailResult
from app.schemas.citations import Citation, EvidenceBundle
from app.schemas.property_context import PropertyContextResult
from app.services.citation_formatter import render_references


@dataclass(slots=True)
class GroundingValidationResult:
    status: str
    citations: list[Citation]
    confidence: str
    errors: list[str]


class GroundingService:
    """Validate structured LLM output against supplied evidence."""

    def validate(self, draft: AnswerDraft, evidence: EvidenceBundle) -> GroundingValidationResult:
        citations_by_id = {citation.id: citation for citation in evidence.citations}
        resolved = [citations_by_id[citation_id] for citation_id in draft.cited_evidence_ids if citation_id in citations_by_id]
        errors: list[str] = []
        if not draft.direct_answer.strip():
            errors.append("missing_direct_answer")
        if not resolved:
            errors.append("missing_citations")
        if len(resolved) < len(draft.cited_evidence_ids):
            errors.append("unknown_citation_ids")

        status = "grounded" if not errors else "insufficient_evidence"
        confidence = draft.confidence
        if status != "grounded" and confidence == "high":
            confidence = "low"
        return GroundingValidationResult(
            status=status,
            citations=resolved,
            confidence=confidence,
            errors=errors,
        )

    def build_response(
        self,
        *,
        draft: AnswerDraft,
        evidence: EvidenceBundle,
        guardrail: GuardrailResult,
        property_context: PropertyContextResult | None,
        validation: GroundingValidationResult,
    ) -> ChatResponse:
        if validation.status != "grounded":
            fallback = self._fallback_answer(property_context=property_context, evidence=evidence)
            return ChatResponse(
                answer=fallback,
                citations=evidence.citations,
                used_property_context=property_context is not None and property_context.status in {"success", "partial"},
                grounding_status=validation.status,
                confidence=validation.confidence,
                follow_up_suggestion="Try asking a narrower zoning question or select a property for a parcel-specific answer.",
                guardrail=guardrail,
            )

        lines = [
            "Direct answer:",
            draft.direct_answer.strip(),
            "",
            "Why:",
        ]
        lines.extend(f"- {item}" for item in draft.why if item.strip())
        lines.append("")
        lines.append("Property context used:")
        if property_context is None:
            lines.append("- No property selected")
        elif property_context.facts_for_prompt:
            lines.extend(f"- {fact.label}: {fact.value}" for fact in property_context.facts_for_prompt)
        else:
            lines.append("- Property lookup was unavailable")
        lines.append("")
        lines.append("References:")
        lines.extend(f"- {reference}" for reference in render_references(validation.citations))
        lines.append("")
        lines.append("Uncertainty / caveats:")
        if draft.uncertainty:
            lines.extend(f"- {item}" for item in draft.uncertainty if item.strip())
        else:
            lines.append("- None noted from the available evidence.")

        return ChatResponse(
            answer="\n".join(lines).strip(),
            citations=validation.citations,
            used_property_context=property_context is not None and property_context.status in {"success", "partial"},
            grounding_status=validation.status,
            confidence=validation.confidence,
            follow_up_suggestion=draft.follow_up_suggestion,
            guardrail=guardrail,
        )

    @staticmethod
    def _fallback_answer(*, property_context: PropertyContextResult | None, evidence: EvidenceBundle) -> str:
        lines = [
            "Direct answer:",
            "I don’t have enough grounded evidence to answer that confidently.",
            "",
            "Why:",
            "- The available zoning evidence did not support a fully cited answer.",
        ]
        if property_context and property_context.error_message:
            lines.append(f"- Property lookup issue: {property_context.error_message}")
        lines.extend(
            [
                "",
                "Property context used:",
                "- No reliable parcel context available" if not property_context else f"- Property lookup status: {property_context.status}",
                "",
                "References:",
            ]
        )
        if evidence.citations:
            lines.extend(f"- {reference}" for reference in render_references(evidence.citations))
        else:
            lines.append("- No authoritative references were available for this answer.")
        lines.extend(
            [
                "",
                "Uncertainty / caveats:",
                "- The assistant is refusing to guess beyond the retrieved evidence.",
            ]
        )
        return "\n".join(lines)

