from __future__ import annotations

from agno.agent import Agent

from zoning_agno.agents.model_factory import ModelFactory, TaskProfile
from zoning_agno.config import Settings
from zoning_agno.models.schemas import ExtractionBatch
from zoning_agno.prompts.instructions import (
    DIMENSIONAL_AGENT_INSTRUCTIONS,
    DISTRICT_AGENT_INSTRUCTIONS,
    OVERLAY_AGENT_INSTRUCTIONS,
    PARKING_AGENT_INSTRUCTIONS,
    USES_AGENT_INSTRUCTIONS,
)


def _schema_for_model(model, schema):
    provider = getattr(model, "provider", "")
    if isinstance(provider, str) and provider.lower() == "groq":
        return None
    return schema



def build_district_agent(settings: Settings, model_factory: ModelFactory | None = None) -> Agent:
    model_factory = model_factory or ModelFactory(settings)
    model = model_factory.create_for_profile(TaskProfile.DISTRICT_EXTRACTION)
    return Agent(
        name="District Agent",
        role="Identify zones, overlays, and typologies",
        model=model,
        instructions=DISTRICT_AGENT_INSTRUCTIONS,
        output_schema=_schema_for_model(model, ExtractionBatch),
        markdown=False,
    )



def build_uses_agent(settings: Settings, model_factory: ModelFactory | None = None) -> Agent:
    model_factory = model_factory or ModelFactory(settings)
    model = model_factory.create_for_profile(TaskProfile.USE_EXTRACTION)
    return Agent(
        name="Uses Agent",
        role="Extract permitted, conditional, and prohibited use rules",
        model=model,
        instructions=USES_AGENT_INSTRUCTIONS,
        output_schema=_schema_for_model(model, ExtractionBatch),
        markdown=False,
    )



def build_dimensional_agent(settings: Settings, model_factory: ModelFactory | None = None) -> Agent:
    return build_general_standards_agent(settings, model_factory=model_factory)


def build_general_standards_agent(settings: Settings, model_factory: ModelFactory | None = None) -> Agent:
    model_factory = model_factory or ModelFactory(settings)
    model = model_factory.create_for_profile(TaskProfile.DIMENSIONAL_EXTRACTION)
    return Agent(
        name="General Standards Agent",
        role="Extract dimensional standards and building envelope controls",
        model=model,
        instructions=DIMENSIONAL_AGENT_INSTRUCTIONS,
        output_schema=_schema_for_model(model, ExtractionBatch),
        markdown=False,
    )



def build_parking_agent(settings: Settings, model_factory: ModelFactory | None = None) -> Agent:
    model_factory = model_factory or ModelFactory(settings)
    model = model_factory.create_for_profile(TaskProfile.PARKING_EXTRACTION)
    return Agent(
        name="Parking Agent",
        role="Extract parking formulas and normalized parking rules",
        model=model,
        instructions=PARKING_AGENT_INSTRUCTIONS,
        output_schema=_schema_for_model(model, ExtractionBatch),
        markdown=False,
    )



def build_overlay_agent(settings: Settings, model_factory: ModelFactory | None = None) -> Agent:
    model_factory = model_factory or ModelFactory(settings)
    model = model_factory.create_for_profile(TaskProfile.OVERLAY_EXTRACTION)
    return Agent(
        name="Overlay Agent",
        role="Extract overlay deltas and superseding rules",
        model=model,
        instructions=OVERLAY_AGENT_INSTRUCTIONS,
        output_schema=_schema_for_model(model, ExtractionBatch),
        markdown=False,
    )
