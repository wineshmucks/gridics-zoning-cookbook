"""Shared market-area context instructions for all agents."""

from __future__ import annotations

MARKET_CONTEXT_INSTRUCTIONS = [
    (
        "If run context includes dependencies.state_env or dependencies.market_area, "
        "treat it as the default market area for this run."
    ),
    (
        "If the user explicitly specifies a different market area in the prompt, "
        "the user-provided market area overrides context defaults."
    ),
]

