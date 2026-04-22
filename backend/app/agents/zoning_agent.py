"""Production-oriented zoning assistant orchestration built on Agno."""

from __future__ import annotations

import os
from textwrap import dedent
from typing import Any

from agno.agent import Agent
from agno.team.mode import TeamMode
from agno.team.team import Team
from agno.models.google import Gemini

from app.agents.storage import get_agno_db
from app.db.session import SessionLocal
from app.services.shared.tenant_service import resolve_tenant_public_config_by_identifier
from app.tools.gridics_property_tool import get_property_context
from app.tools.tenant_context_tool import get_tenant_context
from app.tools.zoning_knowledge_tool import retrieve_zoning_knowledge

AGNO_DB = get_agno_db()
if AGNO_DB is None:
    raise RuntimeError("Agno session storage is enabled but the PostgreSQL session database could not be initialized.")
AGNO_ADD_HISTORY_TO_CONTEXT = True
AGNO_NUM_HISTORY_RUNS = 5
AGNO_STORE_HISTORY_MESSAGES = False
CUSTOMER_ZONING_AGENT_MODEL_ID = "gemini-2.5-flash-lite"
# CODE_RESEARCHER_AGENT_MODEL_ID = "gemini-2.5-pro"
CODE_RESEARCHER_AGENT_MODEL_ID = "gemini-2.5-flash-lite"
PROPERTY_SPECIALIST_AGENT_MODEL_ID = "gemini-2.5-flash-lite"
CUSTOMER_ZONING_TEAM_MODEL_ID = "gemini-2.5-flash-lite"

_GEMINI_API_KEY = (os.getenv("GOOGLE_API_KEY") or "").strip()
if not _GEMINI_API_KEY:
    raise RuntimeError("Set GOOGLE_API_KEY for the Gemini zoning agent.")


def _context_mapping(run_context: Any, key: str, **kwargs: Any) -> dict[str, Any]:
    value = kwargs.get(key)
    if isinstance(value, dict):
        return value
    value = getattr(run_context, key, None)
    return value if isinstance(value, dict) else {}


def _first_context_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _clean_context_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _parse_state_env(value: Any) -> str | None:
    normalized = _clean_context_text(value)
    if normalized is None:
        return None
    candidate = normalized.split(",")[-1].strip().lower()
    if len(candidate) == 2 and candidate.isalpha():
        return candidate
    return None


def _safe_tenant_lookup(client_id: Any, jurisdiction_id: Any) -> Any | None:
    resolved_client_id = _clean_context_text(client_id)
    resolved_jurisdiction_id = _clean_context_text(jurisdiction_id)
    if resolved_client_id is None and resolved_jurisdiction_id is None:
        return None
    try:
        with SessionLocal() as db:
            return resolve_tenant_public_config_by_identifier(
                db,
                client_id=resolved_client_id,
                jurisdiction_id=resolved_jurisdiction_id,
            )
    except Exception as exc:
        print(f"[get_active_tenant_context] Tenant cache lookup failed: {exc}")
        return None


def get_property_facts(lat: float, lng: float, run_context: Any = None, **kwargs: Any) -> dict[str, Any]:
    """Retrieve property-specific zoning facts from Gridics using ONLY coordinates."""
    # 1. Extract client_id from backend injection
    dependencies = _context_mapping(run_context, "dependencies", **kwargs)
    client_id = dependencies.get("client_id")
    
    # 2. Automatically fetch the missing IDs so the LLM doesn't have to!
    tenant_info = get_tenant_context(client_id=client_id)
    jur_id = tenant_info.get("jurisdiction_id")
    state_env = tenant_info.get("state_env")
    
    if not state_env and tenant_info.get("market_served"):
        state_env = _parse_state_env(tenant_info.get("market_served"))
        
    if not jur_id or not state_env:
        return {"status": "error", "error_message": "Backend could not automatically resolve jurisdiction."}
        
    # 3. Call the real tool using the autonomously gathered IDs
    return get_property_context(lat=lat, lng=lng, state_env=state_env, jurisdiction_id=jur_id)


def search_zoning_code(query: str, run_context: Any = None, **kwargs: Any) -> dict[str, Any]:
    """Search the authoritative zoning code for rules and definitions."""
    dependencies = _context_mapping(run_context, "dependencies", **kwargs)
    client_id = dependencies.get("client_id")
    
    tenant_info = get_tenant_context(client_id=client_id)
    jur_id = tenant_info.get("jurisdiction_id")
    
    if not jur_id:
        return {"status": "error", "error_message": "Backend could not automatically resolve jurisdiction."}
        
    return retrieve_zoning_knowledge(jurisdiction_id=jur_id, question=query)


def get_active_tenant_context(run_context: Any = None, **kwargs: Any) -> dict[str, Any]:
    """Return tenant and selected-property values already attached to this run.

    Public assistant and super-admin test runs pass tenant identifiers in
    dependencies. This helper resolves those identifiers through the cached
    tenant config so model-generated tool calls use the Gridics state/instance
    values instead of an organization id or partially populated session value.
    """

    dependencies = _context_mapping(run_context, "dependencies", **kwargs)
    session_state = _context_mapping(run_context, "session_state", **kwargs)
    active_property_context = session_state.get("active_property_context")
    if not isinstance(active_property_context, dict):
        active_property_context = {}

    tenant_config = _safe_tenant_lookup(
        dependencies.get("client_id"),
        _first_context_value(
            dependencies.get("jurisdiction_id"),
            active_property_context.get("jurisdiction_id"),
        ),
    )

    market_served = _first_context_value(
        getattr(tenant_config, "market_served", None),
        dependencies.get("market_served"),
    )
    state_env = _first_context_value(
        _parse_state_env(market_served),
        _parse_state_env(dependencies.get("state_env")),
        _parse_state_env(active_property_context.get("state_env")),
    )
    jurisdiction_id = _first_context_value(
        getattr(tenant_config, "jurisdiction_id", None),
        dependencies.get("jurisdiction_id"),
        active_property_context.get("jurisdiction_id"),
    )
    jurisdiction_name = _first_context_value(
        getattr(tenant_config, "city_name", None),
        dependencies.get("jurisdiction_name"),
        dependencies.get("customer_name"),
        active_property_context.get("jurisdiction_name"),
    )
    client_id = _first_context_value(getattr(tenant_config, "client_id", None), dependencies.get("client_id"))
    customer_name = _first_context_value(getattr(tenant_config, "city_name", None), dependencies.get("customer_name"))
    organization_id = _first_context_value(
        getattr(tenant_config, "clerk_organization_id", None),
        dependencies.get("organization_id"),
    )

    print(
        "[get_active_tenant_context] "
        f"client_id={client_id} "
        f"jurisdiction_id={jurisdiction_id} "
        f"state_env={state_env} "
        f"market_served={market_served} "
        f"cached={tenant_config is not None}"
    )

    return {
        "client_id": client_id,
        "customer_name": customer_name,
        "organization_id": organization_id,
        "jurisdiction_id": jurisdiction_id,
        "jurisdiction_name": jurisdiction_name,
        "state_env": state_env,
        "market_served": market_served,
        "active_property_context": active_property_context or None,
        "property": dependencies.get("property"),
        "found": bool(dependencies.get("client_id") or jurisdiction_id or state_env),
    }


def build_zoning_assistant_agent() -> Agent:
    return Agent(
        id="customer-zoning-agent",
        name="Gridics Zoning Assistant",
        description="Grounded zoning assistant that answers general and property-specific questions with citations.",
        model=Gemini(id=CUSTOMER_ZONING_AGENT_MODEL_ID, api_key=_GEMINI_API_KEY),
        db=AGNO_DB,
        add_history_to_context=AGNO_ADD_HISTORY_TO_CONTEXT,
        num_history_runs=AGNO_NUM_HISTORY_RUNS,
        store_history_messages=AGNO_STORE_HISTORY_MESSAGES,
        session_state={"active_property_context": None},
        add_session_state_to_context=True,
        compress_tool_results=True,
        max_tool_calls_from_history=1,
        tool_call_limit=3,
        enable_agentic_state=False,
        markdown=True,
        use_instruction_tags=True,
        system_message=dedent(
            """
            You are the Gridics AI Zoning Assistant for municipal land use and development workflows.

            Rules:
            - Stay within zoning, land use, development code, overlays, setbacks, parking, bulk, use permissions, FAR, height, density, entitlements, and closely related planning topics.
            - Never fabricate parcel facts, code sections, or references.
            - Use property context only when it was explicitly supplied in the evidence.
            - Prefer direct code references over generic summaries.
            - Distinguish between property facts, zoning/code references, and inference.
            - If evidence is incomplete or conflicting, say so plainly.
            - If there is no property context, do not make parcel-specific conclusions.
            - Keep answers concise, professional, and suitable for planning staff or applicants.

            You must return structured JSON matching the provided schema.
            """
        ),
        instructions=[
            "Generate zoning answers only from the evidence supplied in the user message.",
            "Never invent evidence IDs, parcel facts, or code references.",
            "If no property context was supplied, avoid parcel-specific conclusions.",
            dedent(
                """
                Answer format expectations:
                - `direct_answer`: short direct conclusion grounded in the supplied evidence.
                - `why`: concise bullets explaining the basis for the conclusion.
                - `property_context_used`: only include property facts that were actually provided.
                - `uncertainty`: list missing evidence, conflicts, or limits on certainty.
                - `cited_evidence_ids`: use only evidence IDs that appear in the supplied evidence block.
                - `confidence`: choose `high`, `medium`, or `low` based on evidence quality.
                - `follow_up_suggestion`: optional next step if the user would benefit from a narrower question or a property selection.
                """
            )
        ],
        expected_output="Return structured JSON with direct_answer, why, property_context_used, uncertainty, cited_evidence_ids, confidence, and follow_up_suggestion.",
        tools=[retrieve_zoning_knowledge, get_property_context, get_active_tenant_context, get_tenant_context],
    )


def build_customer_zoning_agent() -> Agent:
    return build_zoning_assistant_agent()


def build_code_researcher_agent() -> Agent:
    print(f'constructing code researcher agent with model {CODE_RESEARCHER_AGENT_MODEL_ID}')
    return Agent(
        id="code-researcher-agent",
        name="Zoning Knowledge Retriever",
        role="Retrieves authoritative zoning code snippets for the current jurisdiction.",
        model=Gemini(id=CODE_RESEARCHER_AGENT_MODEL_ID, api_key=_GEMINI_API_KEY),
        tools=[search_zoning_code], 
        instructions=[
            "Use the `search_zoning_code` tool to find authoritative code passages based on the task given to you.",
            "",
            "### CRITICAL: SEARCH STRATEGY",
            "Vector databases often struggle with highly specific zoning queries because dimensional rules are often in a 'General' chapter rather than the specific 'Zone' chapter.",
            "If your initial search (e.g., 'fence height in T3-O') does not return a specific numerical limit:",
            "1. You MUST call the `search_zoning_code` tool a second time using a broader query.",
            "2. Example: Instead of 'fence height in T3-O', search simply for 'fence height regulations' or 'maximum fence height'.",
            "",
            "### CITATION FORMATTING (MANDATORY)",
            "You MUST append the exact source label or section name to every rule you extract.",
            "Never summarize a rule without including where you found it (e.g., 'Per section 3.7.1, the max height is 6ft')."
        ],
    )

def build_customer_zoning_team() -> Team:
    print(f'constructing customer zoning team with model {CUSTOMER_ZONING_TEAM_MODEL_ID}')
    return Team(
        id="customer_zoning_team",
        name="Lead Zoning Orchestrator",
        description="Coordinates grounded zoning responses across knowledge and property context specialists.",
        model=Gemini(id=CUSTOMER_ZONING_TEAM_MODEL_ID, api_key=_GEMINI_API_KEY),
        members=[build_code_researcher_agent()], 
        
        # FIX 1: Remove get_active_tenant_context and get_tenant_context. 
        # The Team Leader only needs the property context tool now.
        tools=[get_property_facts],
        
        db=AGNO_DB,
        mode=TeamMode.coordinate,
        add_dependencies_to_context=True,
        add_member_tools_to_context=False,
        add_history_to_context=AGNO_ADD_HISTORY_TO_CONTEXT,
        num_history_runs=AGNO_NUM_HISTORY_RUNS,
        store_history_messages=AGNO_STORE_HISTORY_MESSAGES,
        session_state={"active_property_context": None},
        add_session_state_to_context=True,
        enable_agentic_state=True,
        markdown=True,
        enable_user_memories=True,
        enable_agentic_memory=True,
        debug_mode=True,
        instructions=[
            "You are the Lead Zoning Orchestrator. Manage the workflow and synthesize data.",
            "Keep the conversation strictly within zoning, urban planning, and land use scope.",
            "",
            "### CRITICAL: ACTIVE CONTEXT",
            "Your backend has automatically injected the required context into your prompt below:",
            "- CLIENT ID: {client_id}",
            "- ACTIVE PROPERTY: {property}",
            "",
            "If the `ACTIVE PROPERTY` contains coordinates (latitude/longitude), you MUST treat the request as a PROPERTY-SPECIFIC QUESTION.",
            "",
            "### ROUTING WORKFLOW (MANDATORY)",
            "1. PROPERTY-SPECIFIC QUESTIONS:",
            "   If a property is active, you MUST execute the `get_property_facts` tool yourself using the `lat` and `lng`.",
            "   - Read the tool's output to identify the property's Zoning District.",
            "   - **Base Limits:** Use the Gridics tool's specific numbers (e.g., `max_density_units`, `max_height_ft`) as your primary baseline answer.",
            "   - **BONUSES, OVERLAYS & MISSING LIMITS:** If the user asks about a specific bonus (e.g., 'Live Local Act'), overlay, or a limit not returned by Gridics (like fence height):",
            "     a) DELEGATE a task to the 'Zoning Knowledge Retriever'.",
            "     b) The task MUST include the rule to search for AND the Zoning District. (e.g., 'Search for Live Local Act density bonuses in T5-O').",
            "     c) YOU MUST CALCULATE the final yield yourself by multiplying any retrieved bonus limits by the `lot_area_acres` or `lot_area_sqft`.",
            "",
            "2. GENERAL QUESTIONS:",
            "   If NO property is active, DELEGATE directly to the 'Zoning Knowledge Retriever'.",
            "   - Simply pass the user's core question as the task. The Retriever will autonomously handle the jurisdiction routing.",
            "",
            "### FINAL ANSWER FORMATTING & CITATIONS (MANDATORY)",
            "Your final response to the user must be highly readable, scannable, and professionally formatted using Markdown.",
            "",
            "1. DIRECT ANSWER: Start with a clear, concise sentence answering the user's core question.",
            "2. PROPERTY CONTEXT (If applicable): Briefly state the property's Zoning District using bullet points.",
            "3. STRUCTURED RULES: Use bullet points to list specific regulations, dimensions, or allowances. Bold the key terms.",
            "4. EXPLICIT CITATIONS: You MUST explicitly cite the source of your information using the format `(reference: [Source])` immediately at the end of the sentence or bullet point.",
            "   - For pre-calculated math and facts, cite: `(reference: Gridics property data)`.",
            "   - For code rules, cite the exact code section provided by the Knowledge Retriever: `(reference: Sec. 3.7.1 General)`.",
            "",
            "Example of a perfect response layout:",
            "Based on the property's size and zoning, you can build a maximum of 25 units.",
            "",
            "**Property Context:**",
            "- The property is located in the **T5-O** zoning district (reference: Gridics property data).",
            "",
            "**Density Regulations:**",
            "- **Maximum Units:** The specific parcel allows for a maximum of **25 units** (reference: Gridics property data).",
            "- **Base Rule:** The general code allows a maximum density of 150 Dwelling Units per acre in the T5 zone (reference: 5.2.3 Building Function & Density)."
        ],    
    )
