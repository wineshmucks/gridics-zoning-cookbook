from __future__ import annotations

import json
import logging
from typing import Any

from agno.agent import Agent

from zoning_agno.agents.model_factory import ModelFactory, TaskProfile
from zoning_agno.config import Settings
from zoning_agno.schemas import UseLabelInterpretationBundle

logger = logging.getLogger(__name__)

_USE_INTERPRETATION_INSTRUCTIONS = [
    "You map unresolved zoning use labels from a source matrix onto a canonical template use catalog.",
    "Return only JSON matching the requested schema.",
    "Choose zero or more template use names only when they are semantically equivalent or when the template intentionally represents the same legal concept in multiple closely related rows.",
    "Do not invent any template use name not present in the provided catalog.",
    "Do not infer district permissions, conditions, or legal outcomes. This task is only concept alignment.",
    "If there is no clean match, return an empty matched_use_names list.",
    "Keep rationale short and conservative.",
]


def interpret_use_labels(
    *,
    source_labels: list[str],
    template_use_names: list[str],
    settings: Settings,
) -> dict[str, list[str]]:
    """Interpret unresolved source use labels with a narrow, typed Agno step."""
    labels = [item.strip() for item in source_labels if item and item.strip()]
    if not labels:
        return {}
    try:
        agent = _build_agent(settings)
        payload = {
            "task": "Align unresolved source use labels to the provided template use catalog.",
            "source_labels": labels,
            "template_use_names": template_use_names,
        }
        result = agent.run(input=json.dumps(payload, indent=2, ensure_ascii=True))
        bundle = _normalize_bundle(result.content)
    except Exception as exc:
        logger.warning("Use interpretation agent failed; keeping deterministic matching only: %s", exc)
        return {}

    allowed = set(template_use_names)
    resolved: dict[str, list[str]] = {}
    for item in bundle.interpretations:
        matched = [name for name in item.matched_use_names if name in allowed]
        if matched:
            resolved[item.source_label] = matched
    return resolved


def _build_agent(settings: Settings) -> Agent:
    model = ModelFactory(settings).create_for_profile(TaskProfile.USE_EXTRACTION)
    provider = getattr(model, "provider", "")
    output_schema = None if isinstance(provider, str) and provider.lower() == "groq" else UseLabelInterpretationBundle
    return Agent(
        name="Use Label Interpretation Agent",
        role="Map ambiguous source use labels to canonical template use rows",
        model=model,
        instructions=_USE_INTERPRETATION_INSTRUCTIONS,
        output_schema=output_schema,
        markdown=False,
    )


def _normalize_bundle(raw: Any) -> UseLabelInterpretationBundle:
    if isinstance(raw, UseLabelInterpretationBundle):
        return raw
    if isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, dict):
        if "interpretations" not in raw and "items" in raw:
            raw = {"interpretations": raw["items"]}
        return UseLabelInterpretationBundle.model_validate(raw)
    raise TypeError(f"Unsupported interpretation payload type: {type(raw).__name__}")
