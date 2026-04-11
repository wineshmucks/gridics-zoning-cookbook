from __future__ import annotations

from agno.agent import Agent

from zoning_agno.agents.model_factory import ModelFactory, TaskProfile
from zoning_agno.config import Settings
from zoning_agno.models.schemas import ExtractionBatch
from zoning_agno.prompts.instructions import QA_AGENT_INSTRUCTIONS


def _schema_for_model(model, schema):
    provider = getattr(model, "provider", "")
    if isinstance(provider, str) and provider.lower() == "groq":
        return None
    return schema



def build_qa_agent(settings: Settings, model_factory: ModelFactory | None = None) -> Agent:
    model_factory = model_factory or ModelFactory(settings)
    model = model_factory.create_for_profile(TaskProfile.QA_REVIEW)
    return Agent(
        name="QA Agent",
        role="Validate extracted zoning data against evidence",
        model=model,
        instructions=QA_AGENT_INSTRUCTIONS,
        output_schema=_schema_for_model(model, ExtractionBatch),
        markdown=False,
    )
