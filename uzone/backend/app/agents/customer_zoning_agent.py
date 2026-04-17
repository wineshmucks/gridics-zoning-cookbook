from agno.agent import Agent
from agno.run import RunContext
from agno.team import Team, TeamMode

from app.agents.factory import build_agent_model
from app.agents.tools import (
    standardize_address,
    confirm_pending_address,
    analyze_customer_zoning_request,
    query_customer_zoning_code
)

# Your existing hooks (_apply_tenant_assistant_config, _record_run_telemetry, etc.)
# IMPORTANT: Ensure their signatures use `run_context: RunContext` instead of `run_context: Any`
from app.agents.hooks import _apply_tenant_assistant_config, _record_run_telemetry 

# 1. KNOWLEDGE AGENT
code_researcher_agent = Agent(
    id="code-researcher-agent",
    name="Code Researcher",
    role="Search the regulatory text and synthesize general zoning answers.",
    model=build_agent_model(provider="gemini", model_id="gemini-2.5-flash-lite"),
    tools=[query_customer_zoning_code],
    post_hooks=[_record_run_telemetry],
    instructions=[
        "You are a general zoning knowledge specialist.",
        "Only answer based on retrieved documents via `query_customer_zoning_code`.",
        "Provide inline markdown citations mapping to the URL provided in the tool output.",
        "If a user asks a parcel-specific question, refuse and tell the Lead Agent to use the Property Specialist."
    ],
)

# 2. PROPERTY SPECIALIST AGENT
property_specialist_agent = Agent(
    id="property-specialist-agent",
    name="Property Specialist",
    role="Analyze specific parcels using Gridics data and cross-reference with the zoning code.",
    model=build_agent_model(provider="gemini", model_id="gemini-2.5-flash"),
    tools=[analyze_customer_zoning_request, query_customer_zoning_code],
    post_hooks=[_record_run_telemetry],
    instructions=[
        "You are the parcel analysis expert.",
        "1. Immediately call `analyze_customer_zoning_request` to get the active property's Gridics data.",
        "2. Call `query_customer_zoning_code` to find the specific legal text for the Zone and Overlays returned by Gridics.",
        "3. Synthesize a final, grounded property report comparing the data constraints with the legal code."
    ],
)

# 3. LEAD ORCHESTRATOR TEAM
def build_customer_zoning_team() -> Team:
    """Create the Lead Agent that manages the sub-agents and session state."""
    return Team(
        id="customer_zoning_team", 
        name="Lead Zoning Orchestrator",
        description="Triage user requests, standardize addresses, manage confirmations, and delegate tasks.",
        model=build_agent_model(provider="gemini", model_id="gemini-2.5-flash-lite"),
        
        members=[code_researcher_agent, property_specialist_agent],
        tools=[standardize_address, confirm_pending_address],
        
        mode=TeamMode.coordinate, 
        add_member_tools_to_context=True, 
        
        markdown=True,
        # REMOVED: show_tool_calls=False,
        
        # Enable Agno's powerful persistent state
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
            
            "4. FOLLOW-UPS: If the user asks a follow-up about a property (e.g., 'Can I build a pool?'), look at your session state. If `active_property` is set, do not ask for the address again. Delegate straight to the 'Property Specialist'."
        ],
    )

customer_zoning_team = build_customer_zoning_team()
