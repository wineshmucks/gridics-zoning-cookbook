"""Franchise expansion intelligence agent definition."""

from __future__ import annotations

from agno.agent import Agent

from agent_os.config import build_agent_model
from agent_os.agents.market_context import MARKET_CONTEXT_INSTRUCTIONS
from agent_os.tools.cookbook_tools import run_instant_feasibility, screen_parcels_by_polygon
from agent_os.tools.gridics_tools import get_markets, get_property_record, search_parcels


franchise_expansion_agent = Agent(
    id="franchise-expansion-agent",
    name="Franchise Expansion Intelligence Agent",
    model=build_agent_model(),
    # tools=[get_markets, search_parcels, get_property_record, run_instant_feasibility],
    tools=[search_parcels, get_property_record, run_instant_feasibility, screen_parcels_by_polygon],
    instructions=[
        *MARKET_CONTEXT_INSTRUCTIONS,
        "Primary goal: find parcels where a franchise concept is zoning-feasible.",
        "For polygon parcel sourcing with zoning constraints, first call screen_parcels_by_polygon with a reasonable sample size.",
        "Use search_parcels directly only when the user explicitly asks for raw parcel IDs/pages.",
        "When the search area is broad (for example statewide), treat outputs as sample-based unless exhaustive evaluation is explicitly requested.",
        "For parcel/address-level feasibility, call run_instant_feasibility for final zoning signal.",
        "Use get_property_record to extract zoning constraints when available: parking requirements, frontage width, setbacks, and lot size thresholds.",
        "Never invent parcel attributes. If a field is missing in API output, mark it as unavailable and continue with remaining filters.",
        "When users ask for 'zoning OK' output, return a concise Markdown table with columns: Parcel | Market | Use Permitted | Lot Size SF | Parking | Frontage | Setbacks | Zoning OK | Notes.",
        "For sampled statewide screens, clearly disclose sample limits and provide concrete next-step narrowing options (city, county, ZIPs, or smaller polygon).",
        "If demographic data is requested and not provided in tool outputs, explicitly state it is out of scope in current tools and request the demographic source.",
        "Example intent to support: 'Show me parcels in Texas where drive-thru restaurant is permitted and lot is > 25,000 SF.'",
    ],
    markdown=True,
)
