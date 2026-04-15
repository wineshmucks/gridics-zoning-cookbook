from agno.agent import Agent
from agno.team import Team
from agno.models.google import Gemini # Or whatever provider you are using

# Import your tools
from app.agents.tools import (
    standardize_address, 
    confirm_pending_address, 
    analyze_customer_zoning_request, 
    query_customer_zoning_code
)

# 1. Knowledge Agent (General Queries)
code_researcher_agent = Agent(
    id="code-researcher",
    name="Code Researcher",
    role="Search the regulatory text and synthesize general zoning answers.",
    model=Gemini(id="gemini-2.5-flash"),
    tools=[query_customer_zoning_code],
    instructions=[
        "You are a general zoning knowledge specialist.",
        "Only answer based on retrieved documents and provide inline citations.",
        "If a user asks a parcel-specific question (e.g., 'What is the setback for my lot?'), refuse and tell the Lead Agent to use the Property Specialist."
    ],
)

# 2. Property Specialist (Parcel Queries)
property_specialist_agent = Agent(
    id="property-specialist",
    name="Property Specialist",
    role="Analyze specific parcels using Gridics data and cross-reference with the zoning code.",
    model=Gemini(id="gemini-2.5-flash"),
    tools=[analyze_customer_zoning_request, query_customer_zoning_code],
    instructions=[
        "You are the parcel analysis expert.",
        "When invoked, immediately call `analyze_customer_zoning_request` to get the active property's Gridics data.",
        "Then, call `query_customer_zoning_code` to find the specific legal text for the Zone and Overlays returned by Gridics.",
        "Synthesize a final, grounded property report comparing the data constraints with the legal code."
    ],
)

# 3. Lead Orchestrator
customer_zoning_team = Team(
    id="zoning-orchestrator",
    name="Lead Zoning Orchestrator",
    description="Triage user requests, standardize addresses, manage confirmations, and delegate tasks.",
    model=Gemini(id="gemini-2.5-flash"),
    members=[code_researcher_agent, property_specialist_agent],
    tools=[standardize_address, confirm_pending_address],
    
    # Important: Enable persistent session state for memory
    add_session_state_to_context=True,
    session_state={"active_property": None, "pending_property": None},
    
    instructions=[
        "You are the Lead Zoning Consultant overseeing a team.",
        "Follow this exact logic for every request:",
        
        "1. GENERAL QUERY: If the user asks a general zoning question without an address, delegate directly to the 'Code Researcher'.",
        
        "2. SPECIFIC QUERY (NEW ADDRESS): If the user asks about a specific address, call `standardize_address` FIRST.",
        "   - If the tool says 'Stop and ask the user to confirm', you MUST pause delegation and ask the user if the standardized address is correct.",
        
        "3. CONFIRMATION: If the user replies confirming an address, call `confirm_pending_address`.",
        "   - Once confirmed, delegate to the 'Property Specialist' to run the analysis.",
        
        "4. FOLLOW-UPS: If the user asks a follow-up about a property (e.g., 'Can I build a pool?'), look at your session state. If `active_property` is already set, do not ask for the address again. Delegate straight to the 'Property Specialist'.",
        
        "Never make up zoning data yourself. Always rely on your team members."
    ]
)
