"""Zoning property agent definition."""

from __future__ import annotations

from agno.agent import Agent

from agent_os.agents.market_context import MARKET_CONTEXT_INSTRUCTIONS
from agent_os.config import build_agent_model
from agent_os.tools.gridics_tools import get_property_record
from agent_os.tools.zoning_knowledge_tools import query_customer_zoning_code


zoning_agent = Agent(
    id="zoning-agent",
    name="Zoning Property Agent",
    model=build_agent_model(),
    tools=[get_property_record, query_customer_zoning_code],
    instructions=[
        *MARKET_CONTEXT_INSTRUCTIONS,
        "Require state_env, address, and zip_code before running the tool.",
        "Do not invent missing parameters.",
        "When the user asks about a specific customer's zoning code corpus, require client_id and use the zoning knowledge tool.",
    ],
)
