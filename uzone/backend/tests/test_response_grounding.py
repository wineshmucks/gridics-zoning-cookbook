"""Tests for response grounding helpers."""

from __future__ import annotations

from app.services.response_grounding import (
    build_evidence_pack,
    citation_completeness_report,
    grounding_verdict,
)


def test_build_evidence_pack_extracts_unique_section_links() -> None:
    payload = {
        "results": [
            {
                "name": "Sec 1",
                "meta_data": {"section_title": "Section 1", "source_url": "https://example.com/sec1"},
            },
            {
                "name": "Sec 1 duplicate",
                "meta_data": {"section_title": "Section 1", "source_url": "https://example.com/sec1"},
            },
        ]
    }
    evidence = build_evidence_pack(payload)
    assert evidence == [{"section_title": "Section 1", "source_url": "https://example.com/sec1"}]


def test_grounding_verdict_requires_minimum_references() -> None:
    verdict = grounding_verdict([], min_refs=1)
    assert verdict["status"] == "insufficient_evidence"
    assert verdict["answer_ready"] is False


def test_citation_completeness_report_flags_missing_citations() -> None:
    report = citation_completeness_report(
        evidence_pack=[],
        knowledge_payloads=[{"results": [{"name": "Section A", "content": "text"}]}],
    )
    assert report["status"] == "missing_citations"
    assert report["is_complete"] is False
