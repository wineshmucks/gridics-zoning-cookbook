"""Helpers to enforce evidence-grounded assistant responses."""

from __future__ import annotations

from typing import Any


def _iter_results(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    results = payload.get("results")
    return results if isinstance(results, list) else []


def build_evidence_pack(*knowledge_payloads: dict[str, Any] | None) -> list[dict[str, str]]:
    """Extract compact evidence references from one or more knowledge payloads."""
    evidence: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for payload in knowledge_payloads:
        for item in _iter_results(payload):
            metadata = item.get("meta_data") if isinstance(item, dict) else {}
            if not isinstance(metadata, dict):
                metadata = {}
            section_title = str(
                metadata.get("section_title")
                or item.get("name")
                or "Untitled section"
            ).strip()
            source_url = str(metadata.get("source_url") or metadata.get("section_key") or "").strip()
            if not source_url:
                continue
            key = (section_title, source_url)
            if key in seen:
                continue
            seen.add(key)
            evidence.append(
                {
                    "section_title": section_title,
                    "source_url": source_url,
                }
            )
    return evidence


def grounding_verdict(evidence_pack: list[dict[str, str]], *, min_refs: int = 1) -> dict[str, Any]:
    has_enough = len(evidence_pack) >= min_refs
    return {
        "status": "grounded" if has_enough else "insufficient_evidence",
        "evidence_count": len(evidence_pack),
        "min_required": min_refs,
        "answer_ready": has_enough,
    }


def citation_completeness_report(
    *,
    evidence_pack: list[dict[str, str]],
    knowledge_payloads: list[dict[str, Any] | None],
) -> dict[str, Any]:
    """Check whether retrieved knowledge has enough citation references attached."""
    total_knowledge_results = 0
    for payload in knowledge_payloads:
        total_knowledge_results += len(_iter_results(payload))

    evidence_count = len(evidence_pack)
    # Require at least one evidence reference whenever we retrieved knowledge hits.
    is_complete = total_knowledge_results == 0 or evidence_count > 0
    return {
        "status": "complete" if is_complete else "missing_citations",
        "total_knowledge_results": total_knowledge_results,
        "evidence_count": evidence_count,
        "is_complete": is_complete,
    }
