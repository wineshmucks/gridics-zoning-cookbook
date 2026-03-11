"""Agent registry for Gridics cookbook AgentOS."""

from __future__ import annotations

from agent_os.agents.customer_zoning_agent import customer_zoning_agent
from agent_os.agents.franchise_expansion_agent import franchise_expansion_agent
from agent_os.agents.instant_availability_agent import instant_availability_agent
from agent_os.agents.instant_feasibility_agent import instant_feasibility_agent
from agent_os.agents.market_agent import market_agent
from agent_os.agents.search_agent import search_agent
from agent_os.agents.zoning_agent import zoning_agent

ALL_AGENTS = [
    market_agent,
    customer_zoning_agent,
    zoning_agent,
    search_agent,
    instant_feasibility_agent,
    instant_availability_agent,
    franchise_expansion_agent,
]
