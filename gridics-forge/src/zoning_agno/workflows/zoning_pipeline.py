from __future__ import annotations

import json
import logging
from pathlib import Path
import time

from agno.run import RunContext
from agno.workflow.step import Step, StepInput, StepOutput
from agno.workflow.workflow import Workflow

from zoning_agno.agents.teams import build_extraction_team, build_intake_team, build_qa_team
from zoning_agno.config import Settings
from zoning_agno.models.schemas import ExtractionBatch, PipelineInput, PipelineOutput, SourceDocument
from zoning_agno.services.pipeline_service import finalize_pipeline_output, normalize_extraction_batch
from zoning_agno.tools.source_tools import (
    build_source_chunks,
    load_source_document,
    load_source_document_from_cache,
    load_source_document_from_local,
)


logger = logging.getLogger(__name__)


def build_zoning_workflow(settings: Settings) -> Workflow:
    intake_team = build_intake_team(settings)
    extraction_team = build_extraction_team(settings)
    qa_team = build_qa_team(settings)
    team_step_cooldown = max(0, int(getattr(settings, "model_retry_delay_seconds", 1)))
    step_order = ["load-source", "intake", "extract", "qa", "export"]

    def _resume_step_name(session_state: dict[str, object] | None) -> str | None:
        if session_state is None:
            return None
        value = session_state.get("resume_from_step")
        return value if isinstance(value, str) and value in step_order else None

    def _step_index(step_name: str) -> int:
        return step_order.index(step_name)

    def _step_prefix(step_name: str) -> str:
        return f"{_step_index(step_name) + 1:02d}-{step_name}"

    def _legacy_step_dir_name(step_name: str) -> str:
        return step_name

    def _artifact_dir(session_state: dict[str, object] | None) -> Path | None:
        if session_state is None:
            return None
        root = session_state.get("artifact_root")
        if not isinstance(root, str) or not root:
            return None
        path = Path(root) / "workflow_steps"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _migrate_legacy_step_dir(session_state: dict[str, object] | None, step_name: str) -> None:
        artifact_dir = _artifact_dir(session_state)
        if artifact_dir is None:
            return
        legacy_dir = artifact_dir / _legacy_step_dir_name(step_name)
        numbered_dir = artifact_dir / _step_prefix(step_name)
        if legacy_dir.exists() and not numbered_dir.exists():
            legacy_dir.rename(numbered_dir)

    def _dump_artifact(session_state: dict[str, object] | None, step_name: str, phase: str, payload: object) -> None:
        artifact_dir = _artifact_dir(session_state)
        if artifact_dir is None:
            return
        _migrate_legacy_step_dir(session_state, step_name)
        step_dir = artifact_dir / _step_prefix(step_name)
        step_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = step_dir / f"{_step_index(step_name) + 1:02d}-{phase}.json"
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump()
        elif hasattr(payload, "model_dump_json"):
            payload = json.loads(payload.model_dump_json())
        if isinstance(payload, (dict, list)):
            artifact_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        else:
            artifact_path.write_text(json.dumps({"value": str(payload)}, indent=2), encoding="utf-8")

    def _compact_source_summary(document: SourceDocument) -> dict[str, object]:
        return {
            "jurisdiction": document.jurisdiction,
            "source_kind": document.source_kind.value,
            "source_url": document.source_url,
            "document_title": document.document_title,
            "effective_date": document.effective_date,
            "metadata": document.metadata,
            "section_count": len(document.sections),
            "table_count": len(document.tables),
            "definition_count": len(document.definitions),
            "top_sections": [
                {
                    "section_id": section.section_id,
                    "title": section.title,
                    "text_preview": section.text[:400],
                }
                for section in document.sections[:12]
            ],
            "top_tables": [
                {
                    "table_id": table.table_id,
                    "title": table.title,
                    "headers": table.headers,
                    "row_count": len(table.rows),
                }
                for table in document.tables[:6]
            ],
        }

    def _select_source_chunks(document: SourceDocument, step_name: str) -> list[dict[str, object]]:
        all_chunks = [chunk.model_dump(exclude_none=True) for chunk in build_source_chunks(document)]
        keywords_by_step = {
            "intake": ["district", "section", "chapter", "article", "table"],
            "extract": ["district", "use", "parking", "setback", "height", "lot", "area", "far", "bonus"],
            "qa": ["citation", "review", "flag", "district", "rule"],
        }
        keywords = keywords_by_step.get(step_name, [])
        if not keywords:
            return all_chunks[:40]
        selected = [
            chunk
            for chunk in all_chunks
            if any(keyword in f"{chunk.get('title', '')} {chunk.get('text', '')}".lower() for keyword in keywords)
        ]
        return selected[:40] or all_chunks[:20]

    def _batch_chunks(chunks: list[dict[str, object]], batch_size: int) -> list[list[dict[str, object]]]:
        if batch_size <= 0:
            return [chunks]
        return [chunks[idx : idx + batch_size] for idx in range(0, len(chunks), batch_size)]

    def _merge_extraction_batches(batches: list[ExtractionBatch]) -> ExtractionBatch:
        merged = ExtractionBatch()
        for batch in batches:
            merged.districts.extend(batch.districts)
            merged.general_standards.extend(batch.general_standards)
            merged.use_rules.extend(batch.use_rules)
            merged.parking_rules.extend(batch.parking_rules)
            merged.bonus_rules.extend(batch.bonus_rules)
            merged.review_flags.extend(batch.review_flags)
            merged.metadata.update(batch.metadata)
        return merged

    def _load_artifact(session_state: dict[str, object] | None, step_name: str, phase: str) -> object | None:
        artifact_dir = _artifact_dir(session_state)
        if artifact_dir is None:
            return None
        _migrate_legacy_step_dir(session_state, step_name)
        artifact_path = artifact_dir / _step_prefix(step_name) / f"{_step_index(step_name) + 1:02d}-{phase}.json"
        if not artifact_path.exists():
            legacy_artifact_path = artifact_dir / _legacy_step_dir_name(step_name) / f"{phase}.json"
            if legacy_artifact_path.exists():
                artifact_path = legacy_artifact_path
            else:
                return None
        try:
            return json.loads(artifact_path.read_text(encoding="utf-8"))
        except Exception:
            return artifact_path.read_text(encoding="utf-8")

    def _run_team_step(team, step_name: str, step_input: StepInput, session_state: dict[str, object] | None) -> StepOutput:
        if session_state is not None:
            session_state["active_step"] = step_name
        logger.warning("Starting workflow step: %s", step_name)
        resume_from = _resume_step_name(session_state)
        if resume_from is not None and _step_index(step_name) < _step_index(resume_from):
            cached = _load_artifact(session_state, step_name, "output")
            if cached is None:
                cached = step_input.previous_step_content or step_input.input
            logger.warning("Using cached output for step: %s", step_name)
            return StepOutput(content=cached)
        team_input = step_input.previous_step_content or step_input.input
        if session_state is not None and step_name == "extract":
            selected_chunks = session_state.get("selected_source_chunks")
            source_summary = session_state.get("source_summary")
            if isinstance(selected_chunks, list) and selected_chunks:
                batch_results: list[ExtractionBatch] = []
                for batch_index, batch in enumerate(_batch_chunks(selected_chunks, 4), start=1):
                    logger.warning(
                        "Running extract batch %s/%s (%s chunks)",
                        batch_index,
                        (len(selected_chunks) + 3) // 4,
                        len(batch),
                    )
                    batch_payload = {
                        "source_summary": source_summary,
                        "chunks": batch,
                        "batch_index": batch_index,
                        "batch_count": (len(selected_chunks) + 3) // 4,
                    }
                    batch_input = (
                        "SOURCE SUMMARY:\n"
                        f"{json.dumps(source_summary, indent=2, default=str)}\n\n"
                        "CHUNKS:\n"
                        f"{json.dumps(batch, indent=2, default=str)}\n\n"
                        f"BATCH INDEX: {batch_index}\n"
                        f"BATCH COUNT: {(len(selected_chunks) + 3) // 4}\n"
                        "Return a single JSON object matching ExtractionBatch exactly."
                    )
                    _dump_artifact(session_state, step_name, f"input-batch-{batch_index:02d}", batch_payload)
                    result = team.run(input=batch_input, session_state=session_state)
                    _dump_artifact(session_state, step_name, f"output-batch-{batch_index:02d}", result.content)
                    batch_results.append(normalize_extraction_batch(result.content))
                    logger.warning("Finished extract batch %s/%s", batch_index, (len(selected_chunks) + 3) // 4)
                    if team_step_cooldown:
                        time.sleep(team_step_cooldown)
                merged = _merge_extraction_batches(batch_results)
                _dump_artifact(session_state, step_name, "input", {"batch_count": len(batch_results), "chunk_count": len(selected_chunks)})
                _dump_artifact(session_state, step_name, "output", merged)
                logger.warning("Completed workflow step: %s", step_name)
                return StepOutput(content=merged.model_dump())
        elif session_state is not None and step_name in {"intake", "qa"}:
            source_summary = session_state.get("source_summary")
            selected_chunks = session_state.get("selected_source_chunks")
            if isinstance(source_summary, dict):
                chunk_preview = selected_chunks[:8] if isinstance(selected_chunks, list) else []
                team_input = (
                    "SOURCE SUMMARY:\n"
                    f"{json.dumps(source_summary, indent=2, default=str)}\n\n"
                    "CHUNKS:\n"
                    f"{json.dumps(chunk_preview, indent=2, default=str)}\n\n"
                    "Return a single JSON object matching the requested schema exactly."
                )
        if not isinstance(team_input, str):
            team_input = json.dumps(team_input, indent=2, default=str)
        _dump_artifact(session_state, step_name, "input", team_input)
        result = team.run(input=team_input, session_state=session_state)
        _dump_artifact(session_state, step_name, "output", result.content)
        logger.warning("Completed workflow step: %s", step_name)
        if team_step_cooldown:
            time.sleep(team_step_cooldown)
        return StepOutput(content=result.content)

    def load_source(
        step_input: StepInput,
        session_state: dict[str, object] | None = None,
        run_context: RunContext | None = None,
    ) -> StepOutput:
        if session_state is not None:
            session_state["active_step"] = "load-source"
        logger.warning("Starting workflow step: load-source")
        _dump_artifact(session_state, "load-source", "input", step_input.input)
        resume_from = _resume_step_name(session_state)
        if resume_from is not None and _step_index("load-source") < _step_index(resume_from):
            cached = _load_artifact(session_state, "load-source", "output")
            if cached is not None:
                logger.warning("Using cached output for step: load-source")
                return StepOutput(content=cached)
        payload = PipelineInput.model_validate(step_input.input)
        local_source_path = None
        local_html_path = None
        if session_state is not None:
            local_source_path = session_state.get("local_source_path")
            local_html_path = session_state.get("local_html_path")
            local_cache_dir = session_state.get("local_cache_dir")
        else:
            local_cache_dir = None
        if isinstance(local_source_path, str) and local_source_path:
            document = load_source_document(
                source_url=local_source_path,
                jurisdiction=payload.jurisdiction,
                source_kind=payload.source_kind,
            )
        elif isinstance(local_cache_dir, str) and local_cache_dir:
            document = load_source_document_from_cache(local_cache_dir, payload.jurisdiction, payload.source_kind)
        elif isinstance(local_html_path, str) and local_html_path:
            document = load_source_document_from_local(local_html_path, payload.jurisdiction, payload.source_kind)
        else:
            document = load_source_document(
                source_url=payload.source_url,
                jurisdiction=payload.jurisdiction,
                source_kind=payload.source_kind,
            )
        if session_state is not None:
            session_state["source_document"] = document.model_dump()
            session_state["source_metadata"] = document.metadata
            session_state["source_chunks"] = [chunk.model_dump() for chunk in build_source_chunks(document)]
            session_state["selected_source_chunks"] = _select_source_chunks(document, "intake")
            session_state["source_summary"] = _compact_source_summary(document)

        summary = session_state.get("source_summary") if session_state is not None else _compact_source_summary(document)
        if not isinstance(summary, dict):
            summary = _compact_source_summary(document)
        _dump_artifact(
            session_state,
            "load-source",
            "output",
            summary,
        )
        logger.warning("Completed workflow step: load-source")

        return StepOutput(
            content=json.dumps(summary, indent=2, default=str)
        )

    def export_results(
        step_input: StepInput,
        session_state: dict[str, object] | None = None,
        run_context: RunContext | None = None,
    ) -> StepOutput:
        if session_state is None:
            raise ValueError("export step requires workflow session_state")
        session_state["active_step"] = "export"
        logger.warning("Starting workflow step: export")

        payload = PipelineInput.model_validate(session_state.get("pipeline_input"))
        _dump_artifact(session_state, "export", "input", step_input.previous_step_content or step_input.input)
        resume_from = _resume_step_name(session_state)
        if resume_from is not None and _step_index("export") < _step_index(resume_from):
            cached = _load_artifact(session_state, "export", "output")
            if cached is not None:
                logger.warning("Using cached output for step: export")
                return StepOutput(content=cached)
        extraction = normalize_extraction_batch(step_input.previous_step_content)
        extraction.metadata.setdefault("jurisdiction", payload.jurisdiction)
        extraction.metadata.setdefault("source_url", payload.source_url)
        extraction.metadata.setdefault("source_kind", payload.source_kind.value)
        source_document = session_state["source_document"]
        if isinstance(session_state.get("source_metadata"), dict):
            extraction.metadata.update(session_state["source_metadata"])
        if isinstance(session_state.get("source_chunks"), list):
            extraction.metadata.setdefault("source_chunk_count", len(session_state["source_chunks"]))
        # Create a minimal output shell from workflow state.
        pipeline_output = PipelineOutput(
            input=payload,
            source_document=SourceDocument.model_validate(source_document),
            extraction=extraction,
        )
        finalized = finalize_pipeline_output(
            output=pipeline_output,
            out_path=session_state["out_path"],
        )
        _dump_artifact(session_state, "export", "output", finalized)
        logger.warning("Completed workflow step: export")
        return StepOutput(content=finalized.model_dump())

    workflow = Workflow(
        name="zoning-standardization",
        description="Deterministic starter workflow for zoning code standardization",
        steps=[
            Step(name="load-source", executor=load_source),
            Step(name="intake", executor=lambda step_input, session_state=None, run_context=None: _run_team_step(intake_team, "intake", step_input, session_state)),
            Step(name="extract", executor=lambda step_input, session_state=None, run_context=None: _run_team_step(extraction_team, "extract", step_input, session_state)),
            Step(name="qa", executor=lambda step_input, session_state=None, run_context=None: _run_team_step(qa_team, "qa", step_input, session_state)),
            Step(name="export", executor=export_results),
        ],
    )
    return workflow
