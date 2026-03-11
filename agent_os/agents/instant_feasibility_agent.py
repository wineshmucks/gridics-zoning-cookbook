"""Instant feasibility agent definition."""

from __future__ import annotations

from agno.agent import Agent

from agent_os.agents.market_context import MARKET_CONTEXT_INSTRUCTIONS
from agent_os.config import build_agent_model
from agent_os.tools.cookbook_tools import run_instant_feasibility


instant_feasibility_agent = Agent(
    id="instant-feasibility-agent",
    name="Instant Feasibility Agent",
    model=build_agent_model(),
    tools=[run_instant_feasibility],
    instructions=[
        *MARKET_CONTEXT_INSTRUCTIONS,
        "Always call run_instant_feasibility for final result.",
        "Summarize result, confidence, reasons, and next steps.",
    ],
)
