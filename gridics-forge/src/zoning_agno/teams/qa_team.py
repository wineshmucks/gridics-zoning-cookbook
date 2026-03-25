from __future__ import annotations

import json
from dataclasses import dataclass

from zoning_agno.agents.qa import build_qa_agent
from zoning_agno.config import Settings
from zoning_agno.models.schemas import ExtractionBatch
from zoning_agno.services.pipeline_service import normalize_extraction_batch


@dataclass(slots=True)
class QATeam:
    settings: Settings

    def run(self, payload: dict[str, object]) -> ExtractionBatch:
        agent = build_qa_agent(self.settings)
        result = agent.run(input=json.dumps(payload, indent=2, default=str))
        return normalize_extraction_batch(result.content)
