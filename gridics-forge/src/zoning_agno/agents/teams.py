from __future__ import annotations

import logging

from agno.team import Team

from zoning_agno.agents.common import default_team_model
from zoning_agno.agents.extraction import (
    build_dimensional_agent,
    build_district_agent,
    build_overlay_agent,
    build_parking_agent,
    build_uses_agent,
)
from zoning_agno.agents.intake import build_intake_agent
from zoning_agno.agents.model_factory import ModelFactory
from zoning_agno.agents.qa import build_qa_agent
from zoning_agno.config import Settings
from zoning_agno.models.schemas import ExtractionBatch, SourceDocument


logger = logging.getLogger(__name__)


def _schema_for_team_output(team_model, schema):
    provider = getattr(team_model, "provider", "")
    if isinstance(provider, str) and provider.lower() == "groq":
        return None
    return schema


def _step_prefixed_instructions(step_name: str, instructions: list[str]) -> list[str]:
    return [f"WORKFLOW STEP: {step_name}"] + instructions



def build_intake_team(settings: Settings) -> Team:
    logger.warning("Building Intake Team")
    model_factory = ModelFactory(settings)
    intake_agent = build_intake_agent(settings, model_factory=model_factory)
    team_model = default_team_model(settings)
    return Team(
        name="Intake Team",
        members=[intake_agent],
        model=team_model,
        instructions=_step_prefixed_instructions(
            "intake",
            [
            "Create a clean, structured representation of the zoning source.",
            "Preserve legal hierarchy, citations, table structure, and definitions.",
            ],
        ),
        output_schema=_schema_for_team_output(team_model, SourceDocument),
    )



def build_extraction_team(settings: Settings) -> Team:
    logger.warning("Building Extraction Team")
    model_factory = ModelFactory(settings)
    team_model = default_team_model(settings)
    members = [
        build_district_agent(settings, model_factory=model_factory),
        build_uses_agent(settings, model_factory=model_factory),
        build_dimensional_agent(settings, model_factory=model_factory),
        build_parking_agent(settings, model_factory=model_factory),
        build_overlay_agent(settings, model_factory=model_factory),
    ]
    return Team(
        name="Extraction Team",
        members=members,
        model=team_model,
        instructions=_step_prefixed_instructions(
            "extract",
            [
            "Extract a canonical zoning representation from the structured source document.",
            "Prefer explicit citations over inference.",
            "Emit review flags instead of guessing.",
            "Return a single JSON object matching ExtractionBatch exactly.",
            "When the source came from an XLSX export, treat workbook rows as the authoritative source chunks and avoid inventing missing district codes or standards.",
            ],
        ),
        output_schema=_schema_for_team_output(team_model, ExtractionBatch),
    )



def build_qa_team(settings: Settings) -> Team:
    logger.warning("Building QA Team")
    model_factory = ModelFactory(settings)
    qa_agent = build_qa_agent(settings, model_factory=model_factory)
    team_model = default_team_model(settings)
    return Team(
        name="QA Team",
        members=[qa_agent],
        model=team_model,
        instructions=_step_prefixed_instructions(
            "qa",
            [
            "Audit the extraction batch for evidence coverage and internal consistency.",
            "Mark ambiguous or unsupported results for human review.",
            "Return a single JSON object matching ExtractionBatch exactly.",
            ],
        ),
        output_schema=_schema_for_team_output(team_model, ExtractionBatch),
    )
