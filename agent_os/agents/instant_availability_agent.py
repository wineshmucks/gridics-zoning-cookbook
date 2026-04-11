"""Instant availability agent definition."""

from __future__ import annotations

from agno.agent import Agent

from agent_os.agents.market_context import MARKET_CONTEXT_INSTRUCTIONS
from agent_os.config import build_agent_model
from agent_os.tools.cookbook_tools import run_instant_availability


instant_availability_agent = Agent(
    id="instant-availability-agent",
    name="Instant Availability Agent",
    model=build_agent_model(),
    tools=[run_instant_availability],
    instructions=[
        *MARKET_CONTEXT_INSTRUCTIONS,
        "Always call run_instant_availability before finalizing the answer.",
        "Summarize availability result, confidence, constraints, and next steps.",
    ],
)
