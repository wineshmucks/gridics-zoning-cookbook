from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from zoning_agno.agents.extraction import (
    build_district_agent,
    build_general_standards_agent,
    build_overlay_agent,
    build_parking_agent,
    build_uses_agent,
)
from zoning_agno.config import Settings
from zoning_agno.models.schemas import ExtractionBatch
from zoning_agno.services.pipeline_service import normalize_extraction_batch


@dataclass(slots=True)
class ExtractionTeam:
    settings: Settings

    def _run_agent(self, builder: Callable, payload: dict[str, object]) -> ExtractionBatch:
        agent = builder(self.settings)
        result = agent.run(input=json.dumps(payload, indent=2, default=str))
        return normalize_extraction_batch(result.content)

    def run_districts(self, payload: dict[str, object]) -> ExtractionBatch:
        return self._run_agent(build_district_agent, payload)

    def run_uses(self, payload: dict[str, object]) -> ExtractionBatch:
        return self._run_agent(build_uses_agent, payload)

    def run_general_standards(self, payload: dict[str, object]) -> ExtractionBatch:
        return self._run_agent(build_general_standards_agent, payload)

    def run_parking(self, payload: dict[str, object]) -> ExtractionBatch:
        return self._run_agent(build_parking_agent, payload)

    def run_overlays(self, payload: dict[str, object]) -> ExtractionBatch:
        return self._run_agent(build_overlay_agent, payload)
