from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from zoning_agno.exporters.workbook_exporter import WorkbookExporter
from zoning_agno.models.schemas import ExtractionBatch, PipelineOutput, ReviewFlag


def normalize_extraction_batch(raw: Any) -> ExtractionBatch:
    if isinstance(raw, ExtractionBatch):
        return raw

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return ExtractionBatch(
                review_flags=[
                    ReviewFlag(
                        severity="high",
                        sheet_name="workflow",
                        field_key="extraction",
                        issue_type="invalid_output",
                        reason="Model output was not valid JSON.",
                        suggested_action="Review the extraction step output manually.",
                    )
                ]
            )

    if isinstance(raw, dict):
        normalized = dict(raw)
        alias_map = {
            "zoning_districts": "districts",
            "standards": "general_standards",
            "uses": "use_rules",
            "parking": "parking_rules",
            "bonuses": "bonus_rules",
            "flags": "review_flags",
        }
        for alias, target in alias_map.items():
            if alias in normalized and target not in normalized:
                normalized[target] = normalized[alias]
        normalized = _sanitize_extraction_payload(normalized)
        return ExtractionBatch.model_validate(normalized)

    if isinstance(raw, list):
        return ExtractionBatch(
            review_flags=[
                ReviewFlag(
                    severity="high",
                    sheet_name="workflow",
                    field_key="extraction",
                    issue_type="unexpected_list_output",
                    reason="Model returned a list where an ExtractionBatch object was expected.",
                    suggested_action="Review the extraction step output manually.",
                )
            ]
        )

    return ExtractionBatch(
        review_flags=[
            ReviewFlag(
                severity="high",
                sheet_name="workflow",
                field_key="extraction",
                issue_type="unsupported_output",
                reason=f"Unsupported extraction output type: {type(raw).__name__}",
                suggested_action="Review the extraction step output manually.",
            )
        ]
    )


def _sanitize_extraction_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    review_flags = list(normalized.get("review_flags") or [])
    severity_map = {
        "info": "low",
        "warning": "medium",
        "warn": "medium",
        "error": "high",
        "critical": "high",
    }
    valid_families = {"zone", "overlay", "typology"}

    def _coerce_review_flag(flag: Any, *, sheet_name: str | None = None, field_key: str | None = None) -> dict[str, Any] | None:
        if isinstance(flag, dict):
            coerced = dict(flag)
            severity = str(coerced.get("severity") or "medium").strip().lower()
            coerced["severity"] = severity_map.get(severity, severity if severity in {"low", "medium", "high"} else "medium")
            family = coerced.get("family")
            if family is not None:
                normalized_family = str(family).strip().lower()
                coerced["family"] = normalized_family if normalized_family in valid_families else None
            citations = coerced.get("citations")
            if citations is None and "citations_json" in coerced:
                citations = coerced.get("citations_json")
            coerced["citations"] = _coerce_citations(citations)
            if "citations_json" in coerced:
                coerced.pop("citations_json", None)
            if not coerced.get("sheet_name"):
                coerced["sheet_name"] = sheet_name or "workflow"
            if not coerced.get("field_key"):
                coerced["field_key"] = field_key or "review_flags"
            if not coerced.get("reason") and coerced.get("message"):
                coerced["reason"] = coerced["message"]
            if not coerced.get("message") and coerced.get("reason"):
                coerced["message"] = coerced["reason"]
            if not coerced.get("suggested_action"):
                coerced["suggested_action"] = "Review the extraction output manually."
            if not coerced.get("issue_type"):
                coerced["issue_type"] = "model_note"
            return coerced
        if isinstance(flag, str) and flag.strip():
            return {
                "severity": "medium",
                "sheet_name": sheet_name or "workflow",
                "field_key": field_key or "review_flags",
                "issue_type": "model_note",
                "reason": flag.strip(),
                "suggested_action": "Review the extraction output manually.",
            }
        return None

    def _keep_rows(key: str, required_fields: list[str]) -> None:
        rows = normalized.get(key)
        if not isinstance(rows, list):
            return
        kept: list[Any] = []
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                review_flags.append(
                    {
                        "severity": "high",
                        "sheet_name": key,
                        "field_key": f"{key}[{idx}]",
                        "issue_type": "invalid_row_type",
                        "reason": f"Row {idx} in {key} was not an object.",
                        "suggested_action": "Review the extraction output manually.",
                    }
                )
                continue
            row = dict(row)
            for citations_key in ["citations", "citations_json"]:
                if citations_key in row:
                    row[citations_key] = _coerce_citations(row.get(citations_key))
            missing = [field for field in required_fields if not row.get(field)]
            if missing:
                review_flags.append(
                    {
                        "severity": "high",
                        "sheet_name": key,
                        "field_key": f"{key}[{idx}]",
                        "issue_type": "missing_required_fields",
                        "reason": f"Row {idx} in {key} is missing required fields: {', '.join(missing)}.",
                        "suggested_action": "Review the extraction output manually.",
                    }
                )
                continue
            kept.append(row)
        normalized[key] = kept

    _keep_rows("districts", ["code"])
    _keep_rows("general_standards", ["district_code", "field_name", "db_field_name", "data_type"])
    _keep_rows("use_rules", ["district_code", "use_name"])
    _keep_rows("parking_rules", ["district_code", "field_name", "db_field_name"])
    _keep_rows("bonus_rules", ["district_code", "field_name", "db_field_name"])

    coerced_flags: list[dict[str, Any]] = []
    for idx, flag in enumerate(review_flags):
        coerced = _coerce_review_flag(flag, sheet_name="workflow", field_key=f"review_flags[{idx}]")
        if coerced is not None:
            coerced_flags.append(coerced)

    review_flags = coerced_flags
    if review_flags:
        normalized["review_flags"] = review_flags
    return normalized


def _coerce_citations(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    citations: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            quote = item.strip()
            if quote:
                citations.append({"quote": quote, "confidence": 0.0})
            continue
        if not isinstance(item, dict):
            continue
        citation = dict(item)
        quote = str(citation.get("quote") or citation.get("chunk_text") or citation.get("text") or "").strip()
        if not quote:
            title = citation.get("title") or citation.get("section_title") or citation.get("node_id") or "source"
            quote = f"See {title}"
        citation["quote"] = quote
        if "section_title" in citation and "title" not in citation:
            citation["title"] = citation["section_title"]
        if "confidence" not in citation or citation["confidence"] in (None, ""):
            citation["confidence"] = 0.0
        citations.append(citation)
    return citations


def finalize_pipeline_output(
    output: PipelineOutput,
    out_path: str | Path,
    **export_kwargs: Any,
) -> PipelineOutput:
    exporter = WorkbookExporter(output.input.workbook_template_path)
    workbook_path = exporter.export(output.extraction, out_path, **export_kwargs)
    output.extraction.metadata["template_population_stats"] = exporter.last_export_stats
    output.workbook_output_path = str(workbook_path)
    output.status = "needs_review" if output.extraction.review_flags else "ok"
    return output
