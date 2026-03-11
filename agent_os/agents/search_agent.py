"""Parcel search agent definition."""

from __future__ import annotations

from agno.agent import Agent

from agent_os.agents.market_context import MARKET_CONTEXT_INSTRUCTIONS
from agent_os.config import build_agent_model
from agent_os.tools.gridics_tools import search_parcels


search_agent = Agent(
    id="search-agent",
    name="Parcel Search Agent",
    model=build_agent_model(),
    tools=[search_parcels],
    instructions=[
        *MARKET_CONTEXT_INSTRUCTIONS,
        "Use search_parcels for polygon parcel lookup.",
        "Ask for a valid polygon if missing.",
    ],
)
