"""Market availability agent definition."""

from __future__ import annotations

import json
from pathlib import Path

from agno.agent import Agent

from agent_os.agents.market_context import MARKET_CONTEXT_INSTRUCTIONS
from agent_os.config import build_agent_model


_MARKETS_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "markets.json"


def _load_market_names() -> list[str]:
    payload = json.loads(_MARKETS_DATA_PATH.read_text(encoding="utf-8"))
    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {_MARKETS_DATA_PATH} under key 'data'.")
    return [str(item) for item in data]


_MARKET_NAMES = _load_market_names()
_MARKET_NAMES_TEXT = "\n".join(f"- {name}" for name in _MARKET_NAMES)


market_agent = Agent(
    id="market-agent",
    name="Market Availability Agent",
    model=build_agent_model(),
    tools=[],
    instructions=[
        *MARKET_CONTEXT_INSTRUCTIONS,
        "Determine whether a requested market has Gridics coverage using only the static list below.",
        "Determine if the request is for a state and if so, return a list of markets available in the requested state",
        "Always format your final answer as a Markdown table.",
        "Use exactly these columns in this order: Requested Market | Covered | Canonical Covered Market | Notes.",
        "If coverage exists, set Covered to Yes and echo the canonical market name from the list.",
        "If coverage does not exist, set Covered to No, leave Canonical Covered Market as N/A, and suggest the nearest city/county/state alternative in Notes.",
        "Treat punctuation and capitalization differences as equivalent when matching input to a market name.",
        f"Covered markets (source: {_MARKETS_DATA_PATH}):\n{_MARKET_NAMES_TEXT}",
    ],
    markdown=True,
)
