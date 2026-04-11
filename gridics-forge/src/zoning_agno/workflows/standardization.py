from __future__ import annotations

import json
import logging
from pathlib import Path

from agno.run import RunContext
from agno.workflow.step import Step, StepInput, StepOutput
from agno.workflow.workflow import Workflow
from sqlalchemy.orm import Session

from zoning_agno.config import Settings
from zoning_agno.db import create_session_factory
from zoning_agno.db.models import SourceDocumentORM
from zoning_agno.models.schemas import ExtractionBatch, PipelineInput, PipelineOutput, ReviewFlag, SourceDocument, SourceKind, UseRule
from zoning_agno.schemas import AtomicFactBundle, DistrictRegistryBundle, SheetPopulationBundle
from zoning_agno.services.district_registry import (
    build_district_registry,
    build_district_registry_from_template,
    reconcile_extracted_districts_with_template,
)
from zoning_agno.services.fact_extractor import extract_dimensional_facts, extract_parking_facts, extract_use_permission_facts
from zoning_agno.services.pipeline_service import finalize_pipeline_output
from zoning_agno.services.pivot_builder import build_general_pivot_rows
from zoning_agno.services.template_reader import read_template_sheet
from zoning_agno.services.template_mapper import (
    map_bonus_facts_to_template_rows,
    map_general_facts_to_template_rows,
    map_parking_facts_to_template_rows,
    map_use_capacity_facts_to_template_rows,
    map_use_facts_to_template_rows,
)


logger = logging.getLogger(__name__)


def build_zoning_standardization_workflow(settings: Settings) -> Workflow:
    session_factory = create_session_factory(settings)

    def _dump(session_state: dict[str, object] | None, step_name: str, payload: object) -> None:
        if session_state is None:
            return
        root = session_state.get("artifact_root")
        if not isinstance(root, str) or not root:
            return
        path = Path(root) / "workflow_steps" / step_name
        path.mkdir(parents=True, exist_ok=True)
        output = payload.model_dump() if hasattr(payload, "model_dump") else payload
        (path / "output.json").write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")

    def _log_phase(phase_number: int, phase_name: str, message: str, **details: object) -> None:
        detail_parts = [f"{key}={value}" for key, value in details.items()]
        suffix = f" | {' '.join(detail_parts)}" if detail_parts else ""
        logger.info("PHASE %s - %s: %s%s", phase_number, phase_name, message, suffix)

    def _resolve_source_document_id(payload: PipelineInput, session_state: dict[str, object] | None) -> int:
        source_document_id = payload.source_document_id
        if source_document_id is None and session_state is not None:
            candidate = session_state.get("source_document_id")
            if isinstance(candidate, int):
                source_document_id = candidate
        if source_document_id is None:
            raise ValueError("Workflow requires source_document_id in PipelineInput or session_state.")
        return source_document_id

    def _legacy_extraction_from_registry_and_facts(
        source_document_id: int,
        district_registry: DistrictRegistryBundle,
        dimensional_facts: AtomicFactBundle,
    ) -> ExtractionBatch:
        def _legacy_citation(citation) -> dict[str, object]:
            return {
                "section_id": str(citation.section_id) if citation.section_id is not None else None,
                "section_title": citation.title,
                "quote": citation.quote,
                "source_url": citation.source_url,
                "confidence": citation.confidence,
            }

        extraction = ExtractionBatch(
            districts=[
                {
                    "code": record.district_code,
                    "name": record.district_name,
                    "family": record.district_family or "zone",
                    "citations": [_legacy_citation(citation) for citation in record.citations],
                    "confidence": record.confidence,
                }
                for record in district_registry.districts
            ],
            general_standards=[
                {
                    "district_code": fact.district_code,
                    "family": "zone",
                    "field_name": fact.field_name,
                    "db_field_name": fact.field_name,
                    "data_type": "number" if fact.value_numeric is not None else "text",
                    "value": fact.value_numeric if fact.value_numeric is not None else fact.value_text,
                    "unit": fact.unit,
                    "conditions": [],
                    "exceptions": [fact.exception_text] if fact.exception_text else [],
                    "citations": [_legacy_citation(citation) for citation in fact.citations],
                }
                for fact in dimensional_facts.facts
                if fact.fact_type == "dimensional_standard" and fact.district_code and fact.field_name
            ],
            review_flags=[],
            metadata={
                "source_document_id": source_document_id,
                "district_registry_count": len(district_registry.districts),
                "dimensional_fact_count": len(dimensional_facts.facts),
            },
        )
        for fact in dimensional_facts.facts:
            if not fact.requires_human_review:
                continue
            extraction.review_flags.append(
                ReviewFlag(
                    severity="medium",
                    sheet_name="Zones - General",
                    field_key=fact.field_name or "unknown_fact",
                    issue_type="ambiguous_fact",
                    reason=f"Dimensional fact needs review for district={fact.district_code or 'unknown'} field={fact.field_name or 'unknown'}.",
                    suggested_action="Review the source text and confirm the dimensional fact before relying on this value.",
                    district_code=fact.district_code,
                    citations=[_legacy_citation(citation) for citation in fact.citations],
                )
            )
        if not district_registry.districts:
            extraction.review_flags.append(
                ReviewFlag(
                    severity="high",
                    sheet_name="workflow",
                    field_key="district_registry",
                    issue_type="missing_district_registry",
                    reason="No zoning districts were discovered for the source document.",
                    suggested_action="Review district discovery logic and source headings/tables.",
                )
            )
        if not extraction.general_standards:
            extraction.review_flags.append(
                ReviewFlag(
                    severity="high",
                    sheet_name="Zones - General",
                    field_key="general_standards",
                    issue_type="missing_dimensional_facts",
                    reason="No dimensional standards were extracted into atomic facts.",
                    suggested_action="Review dimensional fact extraction patterns and source content.",
                )
            )
        return extraction

    def load_source_metadata(step_input: StepInput, session_state: dict[str, object] | None = None, run_context: RunContext | None = None) -> StepOutput:
        payload = PipelineInput.model_validate(step_input.input)
        source_document_id = _resolve_source_document_id(payload, session_state)
        _log_phase(1, "load-source-metadata", "starting", source_document_id=source_document_id)
        with session_factory() as session:
            source = session.get(SourceDocumentORM, source_document_id)
            if source is None:
                raise ValueError(f"Source document not found: {source_document_id}")
            response = {
                "pipeline_input": payload.model_dump(),
                "source_document_id": source_document_id,
                "source_document": {
                    "jurisdiction": source.jurisdiction,
                    "source_kind": SourceKind(source.source_type).value if source.source_type else SourceKind.MUNICODE.value,
                    "source_url": source.source_url or payload.source_url,
                    "document_title": source.source_file_name,
                    "metadata": {
                        "source_document_id": source_document_id,
                        "imported_at": str(source.imported_at),
                        "source_file_path": source.source_url,
                    },
                },
            }
        if session_state is not None:
            session_state["pipeline_input"] = payload.model_dump()
            session_state["source_document_id"] = source_document_id
            session_state["source_document"] = response["source_document"]
        _log_phase(
            1,
            "load-source-metadata",
            "completed",
            jurisdiction=source.jurisdiction,
            source_file=source.source_file_name,
            source_path=source.source_url,
            template_path=payload.workbook_template_path,
        )
        _dump(session_state, "01-load-source-metadata", response)
        return StepOutput(content=response)

    def build_registry(step_input: StepInput, session_state: dict[str, object] | None = None, run_context: RunContext | None = None) -> StepOutput:
        previous = step_input.previous_step_content or step_input.input
        source_document_id = int(previous["source_document_id"])
        _log_phase(2, "build-district-registry", "starting", source_document_id=source_document_id)
        payload = PipelineInput.model_validate(previous["pipeline_input"])
        template_sheet = read_template_sheet(payload.workbook_template_path, "Zones - General")
        template_registry = build_district_registry_from_template(template_sheet)
        with session_factory() as session:
            extracted_registry = build_district_registry(session, source_document_id)
        district_registry = reconcile_extracted_districts_with_template(template_registry, extracted_registry)
        _log_phase(2, "build-district-registry", "completed", district_count=len(district_registry.districts))
        response = {
            **previous,
            "district_registry": district_registry.model_dump(),
            "district_registry_summary": {
                "district_codes": [record.district_code for record in district_registry.districts],
                "district_count": len(district_registry.districts),
            },
        }
        _dump(session_state, "02-build-district-registry", response)
        return StepOutput(content=response)

    def extract_dimensional_atomic_facts(step_input: StepInput, session_state: dict[str, object] | None = None, run_context: RunContext | None = None) -> StepOutput:
        previous = step_input.previous_step_content or step_input.input
        source_document_id = int(previous["source_document_id"])
        district_registry = DistrictRegistryBundle.model_validate(previous["district_registry"])
        _log_phase(3, "extract-dimensional-facts", "starting", district_count=len(district_registry.districts))
        with session_factory() as session:
            facts = extract_dimensional_facts(session, source_document_id, district_registry)
        _log_phase(3, "extract-dimensional-facts", "completed", fact_count=len(facts.facts))
        response = {
            **previous,
            "dimensional_facts": facts.model_dump(),
            "fact_counts": {
                "dimensional_standard": len(facts.facts),
            },
        }
        _dump(session_state, "03-extract-dimensional-facts", response)
        return StepOutput(content=response)

    def extract_use_atomic_facts(step_input: StepInput, session_state: dict[str, object] | None = None, run_context: RunContext | None = None) -> StepOutput:
        previous = step_input.previous_step_content or step_input.input
        source_document_id = int(previous["source_document_id"])
        payload = PipelineInput.model_validate(previous["pipeline_input"])
        district_registry = DistrictRegistryBundle.model_validate(previous["district_registry"])
        use_template = read_template_sheet(payload.workbook_template_path, "Zones - Uses")
        _log_phase(4, "extract-use-facts", "starting", district_count=len(district_registry.districts))
        with session_factory() as session:
            facts = extract_use_permission_facts(
                session,
                source_document_id,
                district_registry,
                template_sheet=use_template,
            )
        _log_phase(4, "extract-use-facts", "completed", fact_count=len(facts.facts))
        response = {
            **previous,
            "use_facts": facts.model_dump(),
            "fact_counts": {
                **previous.get("fact_counts", {}),
                "use_permission": len(facts.facts),
            },
        }
        _dump(session_state, "04-extract-use-facts", response)
        return StepOutput(content=response)

    def build_general_pivot(step_input: StepInput, session_state: dict[str, object] | None = None, run_context: RunContext | None = None) -> StepOutput:
        previous = step_input.previous_step_content or step_input.input
        district_registry = DistrictRegistryBundle.model_validate(previous["district_registry"])
        dimensional_facts = AtomicFactBundle.model_validate(previous["dimensional_facts"])
        _log_phase(5, "build-general-pivot", "starting", fact_count=len(dimensional_facts.facts))
        general_pivot = build_general_pivot_rows(district_registry, dimensional_facts)
        _log_phase(5, "build-general-pivot", "completed", row_count=len(general_pivot.rows), district_columns=len(general_pivot.district_codes))
        response = {
            **previous,
            "general_pivot": general_pivot.model_dump(),
            "pivot_counts": {
                general_pivot.sheet_name: len(general_pivot.rows),
            },
        }
        _dump(session_state, "05-build-general-pivot", response)
        return StepOutput(content=response)

    def build_general_population(step_input: StepInput, session_state: dict[str, object] | None = None, run_context: RunContext | None = None) -> StepOutput:
        previous = step_input.previous_step_content or step_input.input
        payload = PipelineInput.model_validate(previous["pipeline_input"])
        dimensional_facts = AtomicFactBundle.model_validate(previous["dimensional_facts"])
        template_sheet = read_template_sheet(payload.workbook_template_path, "Zones - General")
        bundle = map_general_facts_to_template_rows(template_sheet, dimensional_facts)
        _log_phase(6, "build-general-population", "completed", populated_cells=len(bundle.populated_cells))
        response = {**previous, "general_population": bundle.model_dump()}
        _dump(session_state, "06-build-general-population", response)
        return StepOutput(content=response)

    def build_use_population(step_input: StepInput, session_state: dict[str, object] | None = None, run_context: RunContext | None = None) -> StepOutput:
        previous = step_input.previous_step_content or step_input.input
        payload = PipelineInput.model_validate(previous["pipeline_input"])
        use_facts = AtomicFactBundle.model_validate(previous["use_facts"])
        template_sheet = read_template_sheet(payload.workbook_template_path, "Zones - Uses")
        bundle = map_use_facts_to_template_rows(template_sheet, use_facts)
        _log_phase(7, "build-use-population", "completed", populated_cells=len(bundle.populated_cells))
        response = {**previous, "use_population": bundle.model_dump()}
        _dump(session_state, "07-build-use-population", response)
        return StepOutput(content=response)

    def extract_parking_atomic_facts(step_input: StepInput, session_state: dict[str, object] | None = None, run_context: RunContext | None = None) -> StepOutput:
        previous = step_input.previous_step_content or step_input.input
        source_document_id = int(previous["source_document_id"])
        district_registry = DistrictRegistryBundle.model_validate(previous["district_registry"])
        _log_phase(8, "extract-parking-facts", "starting", district_count=len(district_registry.districts))
        with session_factory() as session:
            facts = extract_parking_facts(session, source_document_id, district_registry)
        _log_phase(8, "extract-parking-facts", "completed", fact_count=len(facts.facts))
        response = {
            **previous,
            "parking_facts": facts.model_dump(),
            "fact_counts": {
                **previous.get("fact_counts", {}),
                "parking_rule": len(facts.facts),
            },
        }
        _dump(session_state, "08-extract-parking-facts", response)
        return StepOutput(content=response)

    def build_parking_population(step_input: StepInput, session_state: dict[str, object] | None = None, run_context: RunContext | None = None) -> StepOutput:
        previous = step_input.previous_step_content or step_input.input
        payload = PipelineInput.model_validate(previous["pipeline_input"])
        parking_facts = AtomicFactBundle.model_validate(previous["parking_facts"])
        template_sheet = read_template_sheet(payload.workbook_template_path, "Zones - Parking")
        bundle = map_parking_facts_to_template_rows(template_sheet, parking_facts)
        _log_phase(9, "build-parking-population", "completed", populated_cells=len(bundle.populated_cells))
        response = {**previous, "parking_population": bundle.model_dump()}
        _dump(session_state, "09-build-parking-population", response)
        return StepOutput(content=response)

    def build_use_capacity_population(step_input: StepInput, session_state: dict[str, object] | None = None, run_context: RunContext | None = None) -> StepOutput:
        previous = step_input.previous_step_content or step_input.input
        payload = PipelineInput.model_validate(previous["pipeline_input"])
        dimensional_facts = AtomicFactBundle.model_validate(previous["dimensional_facts"])
        template_sheet = read_template_sheet(payload.workbook_template_path, "Zones - Use Capacity")
        bundle = map_use_capacity_facts_to_template_rows(template_sheet, dimensional_facts)
        _log_phase(10, "build-use-capacity-population", "completed", populated_cells=len(bundle.populated_cells))
        response = {**previous, "use_capacity_population": bundle.model_dump()}
        _dump(session_state, "10-build-use-capacity-population", response)
        return StepOutput(content=response)

    def build_bonus_population(step_input: StepInput, session_state: dict[str, object] | None = None, run_context: RunContext | None = None) -> StepOutput:
        previous = step_input.previous_step_content or step_input.input
        payload = PipelineInput.model_validate(previous["pipeline_input"])
        empty_facts = AtomicFactBundle()
        template_sheet = read_template_sheet(payload.workbook_template_path, "Zones - Bonus")
        bundle = map_bonus_facts_to_template_rows(template_sheet, empty_facts)
        _log_phase(11, "build-bonus-population", "completed", populated_cells=len(bundle.populated_cells))
        response = {**previous, "bonus_population": bundle.model_dump()}
        _dump(session_state, "11-build-bonus-population", response)
        return StepOutput(content=response)

    def run_qa(step_input: StepInput, session_state: dict[str, object] | None = None, run_context: RunContext | None = None) -> StepOutput:
        previous = step_input.previous_step_content or step_input.input
        source_document_id = int(previous["source_document_id"])
        district_registry = DistrictRegistryBundle.model_validate(previous["district_registry"])
        dimensional_facts = AtomicFactBundle.model_validate(previous["dimensional_facts"])
        use_facts = AtomicFactBundle.model_validate(previous["use_facts"])
        _log_phase(12, "run-qa", "starting")
        final_extraction = _legacy_extraction_from_registry_and_facts(source_document_id, district_registry, dimensional_facts)
        def _legacy_citation(citation) -> dict[str, object]:
            return {
                "section_id": str(citation.section_id) if citation.section_id is not None else None,
                "section_title": citation.title,
                "quote": citation.quote,
                "source_url": citation.source_url,
                "confidence": citation.confidence,
            }
        for fact in use_facts.facts:
            if not fact.district_code or not fact.value_text:
                continue
            final_extraction.use_rules.append(
                UseRule(
                    district_code=fact.district_code,
                    family="zone",
                    use_label_id=None,
                    use_name=(fact.value_json or {}).get("use_name") or (fact.use_key or "unknown_use"),
                    use_value=fact.value_text,
                    conditions=[],
                    exceptions=[],
                    citations=[_legacy_citation(citation) for citation in fact.citations],
                )
            )
        _log_phase(
            12,
            "run-qa",
            "completed",
            districts=len(final_extraction.districts),
            general_standards=len(final_extraction.general_standards),
            use_rules=len(final_extraction.use_rules),
            review_flags=len(final_extraction.review_flags),
        )
        response = {**previous, "final_extraction": final_extraction.model_dump()}
        _dump(session_state, "12-run-qa", response)
        return StepOutput(content=response)

    def export_workbook(step_input: StepInput, session_state: dict[str, object] | None = None, run_context: RunContext | None = None) -> StepOutput:
        if session_state is None:
            raise ValueError("export-workbook step requires session_state")
        previous = step_input.previous_step_content or step_input.input
        _log_phase(13, "export-workbook", "starting", out_path=session_state["out_path"])
        payload = PipelineInput.model_validate(previous["pipeline_input"])
        source_document = SourceDocument.model_validate(previous["source_document"])
        extraction = ExtractionBatch.model_validate(previous["final_extraction"])
        district_registry = DistrictRegistryBundle.model_validate(previous["district_registry"])
        general_population = SheetPopulationBundle.model_validate(previous["general_population"])
        use_population = SheetPopulationBundle.model_validate(previous["use_population"])
        parking_population = SheetPopulationBundle.model_validate(previous["parking_population"])
        use_capacity_population = SheetPopulationBundle.model_validate(previous["use_capacity_population"])
        bonus_population = SheetPopulationBundle.model_validate(previous["bonus_population"])
        output = PipelineOutput(input=payload, source_document=source_document, extraction=extraction)
        finalized = finalize_pipeline_output(
            output,
            session_state["out_path"],
            district_registry=district_registry,
            general_population=general_population,
            use_population=use_population,
            parking_population=parking_population,
            use_capacity_population=use_capacity_population,
            bonus_population=bonus_population,
        )
        _log_phase(13, "export-workbook", "completed", workbook_output_path=finalized.workbook_output_path, status=finalized.status)
        response = {**previous, "pipeline_output": finalized.model_dump()}
        _dump(session_state, "13-export-workbook", response)
        return StepOutput(content=response)

    def emit_review_queue(step_input: StepInput, session_state: dict[str, object] | None = None, run_context: RunContext | None = None) -> StepOutput:
        previous = step_input.previous_step_content or step_input.input
        review_flag_count = len(previous["pipeline_output"]["extraction"].get("review_flags") or [])
        _log_phase(14, "emit-review-queue", "completed", review_flags=review_flag_count)
        response = previous["pipeline_output"]
        _dump(session_state, "14-emit-review-queue", response)
        return StepOutput(content=response)

    return Workflow(
        name="zoning-standardization-pivot-foundation",
        description="Deterministic district-registry and dimensional-pivot workflow",
        steps=[
            Step(name="load-source-metadata", executor=load_source_metadata),
            Step(name="build-district-registry", executor=build_registry),
            Step(name="extract-dimensional-facts", executor=extract_dimensional_atomic_facts),
            Step(name="extract-use-facts", executor=extract_use_atomic_facts),
            Step(name="build-general-pivot", executor=build_general_pivot),
            Step(name="build-general-population", executor=build_general_population),
            Step(name="build-use-population", executor=build_use_population),
            Step(name="extract-parking-facts", executor=extract_parking_atomic_facts),
            Step(name="build-parking-population", executor=build_parking_population),
            Step(name="build-use-capacity-population", executor=build_use_capacity_population),
            Step(name="build-bonus-population", executor=build_bonus_population),
            Step(name="run-qa", executor=run_qa),
            Step(name="export-workbook", executor=export_workbook),
            Step(name="emit-review-queue", executor=emit_review_queue),
        ],
    )
