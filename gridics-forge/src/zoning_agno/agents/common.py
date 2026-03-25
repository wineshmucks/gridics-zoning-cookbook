from __future__ import annotations

from zoning_agno.agents.model_factory import ModelFactory, TaskProfile
from zoning_agno.config import Settings


def build_model_factory(settings: Settings) -> ModelFactory:
    return ModelFactory(settings)



def default_team_model(settings: Settings):
    return build_model_factory(settings).create_for_profile(TaskProfile.TEAM_COORDINATOR)
