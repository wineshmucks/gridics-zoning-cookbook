from __future__ import annotations

from agno.team.team import Team
from agno.team.mode import TeamMode

from app.agents.factory import create_agent
from app.agents.tools import (
    analyze_customer_zoning_request,
    confirm_pending_address,
    query_customer_zoning_code,
    standardize_address,
)

# Import our extracted hooks
from app.agents.agent_hooks import (
    _apply_model_override,
    _restore_model_override,
    _apply_tenant_assistant_config,
    _record_run_telemetry,
)

# ------------------------------------------------------------------------
# Agent Definitions
# ------------------------------------------------------------------------

code_researcher_agent = create_agent(
    id="code-researcher-agent",
    name="Code Researcher",
    role="Search the regulatory text and synthesize general zoning answers.",
    model=None,
    tools=[query_customer_zoning_code],
    post_hooks=[_record_run_telemetry],
    instructions=[
        "You are a general zoning knowledge specialist.",
        "Only answer based on retrieved documents via `query_customer_zoning_code`.",
        "Provide inline markdown citations mapping to the URL provided in the tool output.",
        "If a user asks a parcel-specific question, refuse and tell the Lead Agent to use the Property Specialist.",
    ],
)

property_specialist_agent = create_agent(
    id="property-specialist-agent",
    name="Property Specialist",
    role="Analyze specific parcels using Gridics data and cross-reference with the zoning code.",
    model=None,
    tools=[analyze_customer_zoning_request, query_customer_zoning_code],
    post_hooks=[_record_run_telemetry],
    instructions=[
        "You are the parcel analysis expert.",
        "1. Immediately call `analyze_customer_zoning_request` to get the active property's Gridics data.",
        "2. Call `query_customer_zoning_code` to find the specific legal text for the Zone and Overlays returned by Gridics.",
        "3. Synthesize a final, grounded property report comparing the data constraints with the legal code.",
    ],
)


def build_customer_zoning_team() -> Team:
    """Create the Lead Agent that manages the sub-agents and session state."""
    return Team(
        id="customer_zoning_team",
        name="Lead Zoning Orchestrator",
        description="Triage user requests, standardize addresses, manage confirmations, and delegate tasks.",
        model=None,
        members=[code_researcher_agent, property_specialist_agent],
        tools=[standardize_address, confirm_pending_address],
        mode=TeamMode.coordinate,
        add_member_tools_to_context=True,
        markdown=True,
        add_session_state_to_context=True,
        session_state={"active_property": None, "pending_property": None, "gridics_summary": None},
        pre_hooks=[_apply_tenant_assistant_config],
        post_hooks=[_record_run_telemetry],
        instructions=[
            "You are the Lead Zoning Consultant overseeing a multi-agent team.",
            "TONE: Act highly knowledgeable and friendly.",
            "--- ROUTING LOGIC ---",
            "1. GENERAL QUERY: If the user asks a general zoning question without an address, delegate directly to the 'Code Researcher'.",
            "2. SPECIFIC QUERY (NEW ADDRESS): If the user asks about a specific address, call `standardize_address` FIRST.",
            "   - If the tool says 'STOP DELEGATING', you MUST reply directly to the user asking them to confirm the standardized address.",
            "3. CONFIRMATION: If the user replies confirming an address, call `confirm_pending_address`.",
            "   - Once confirmed, delegate to the 'Property Specialist' to run the parcel analysis.",
            "4. FOLLOW-UPS: If the user asks a follow-up about a property (e.g., 'Can I build a pool?'), look at your session state. If `active_property` is set, do not ask for the address again. Delegate straight to the 'Property Specialist'.",
        ],
    )


customer_zoning_team = build_customer_zoning_team()

customer_zoning_agent = create_agent(
    id="customer-zoning-agent",
    name="Customer Zoning Agent",
    description=(
        "Gridics parcel data assistant that drafts a Zoning Memorandum and routes follow-up questions "
        "through a two-step confirmation flow."
    ),
    model=None,
    tools=[
        standardize_address,
        confirm_pending_address,
        analyze_customer_zoning_request,
        query_customer_zoning_code,
    ],
    session_state={"active_property_context": None},
    add_session_state_to_context=True,
    add_history_to_context=True,
    num_history_runs=1,
    max_tool_calls_from_history=1,
    enable_agentic_state=False,
    compress_tool_results=True,
    tool_call_limit=3,
    use_instruction_tags=True,
    expected_output=(
        "Return a polished Zoning Memorandum grounded in Gridics parcel data and the zoning code. "
        "Never output your internal thought process."
    ),
    pre_hooks=[_apply_tenant_assistant_config, _apply_model_override],
    post_hooks=[_restore_model_override, _record_run_telemetry],
    instructions=[
        "You are the customer zoning lead agent.",
        "When the session state contains needs_confirmation: true, confirm the address before continuing.",
        "If the user replies with a short yes, yes continue, or go ahead, treat that as confirmation.",
        "If the address is still ambiguous, ask a brief follow-up instead of assuming a parcel.",
        "Only use the Gridics-backed tools for parcel-specific claims.",
    ],
)
