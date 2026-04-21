"""Local Agno registry for UZone agents and teams."""

from __future__ import annotations

from app.agents.customer_zoning_agent import customer_zoning_agent, customer_zoning_team

ALL_AGENTS = [customer_zoning_agent]
ALL_TEAMS = [customer_zoning_team]
