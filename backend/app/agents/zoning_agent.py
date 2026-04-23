"""Production-oriented zoning assistant orchestration built on Agno."""

from __future__ import annotations

import os
import warnings
from textwrap import dedent
from typing import Any

from agno.agent import Agent
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

CUSTOMER_ZONING_AGENT_MODEL_ID = "gemini-2.5-flash"
CUSTOMER_ZONING_AGENT_PRO_MODEL_ID = "gemini-2.5-pro"
CODE_RESEARCHER_AGENT_MODEL_ID = CUSTOMER_ZONING_AGENT_MODEL_ID

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


def _get_run_metadata(*, run_context: Any = None, metadata: Any = None, **kwargs: Any) -> dict[str, Any]:
    candidate = metadata if isinstance(metadata, dict) else None
    if candidate is not None:
        return candidate

    context_metadata = _context_mapping(run_context, "metadata", **kwargs)
    return context_metadata if isinstance(context_metadata, dict) else {}


def _is_pro_mode(*, run_context: Any = None, metadata: Any = None, **kwargs: Any) -> bool:
    resolved_metadata = _get_run_metadata(run_context=run_context, metadata=metadata, **kwargs)
    mode = str(resolved_metadata.get("assistant_mode") or "").strip().lower()
    if mode:
        return mode == "pro"

    requested_model_id = str(resolved_metadata.get("assistant_model_id") or "").strip().lower()
    return requested_model_id == CUSTOMER_ZONING_AGENT_PRO_MODEL_ID


def _resolve_customer_zoning_model_id(*, run_context: Any = None, metadata: Any = None, **kwargs: Any) -> str:
    if _is_pro_mode(run_context=run_context, metadata=metadata, **kwargs):
        return CUSTOMER_ZONING_AGENT_PRO_MODEL_ID
    return CUSTOMER_ZONING_AGENT_MODEL_ID


def get_property_facts(lat: float, lng: float, run_context: Any = None, **kwargs: Any) -> dict[str, Any]:
    """Retrieve property-specific zoning facts from Gridics using ONLY coordinates."""
    dependencies = _context_mapping(run_context, "dependencies", **kwargs)
    client_id = dependencies.get("client_id")

    tenant_info = get_tenant_context(client_id=client_id)
    jur_id = tenant_info.get("jurisdiction_id")
    state_env = tenant_info.get("state_env")

    if not state_env and tenant_info.get("market_served"):
        state_env = _parse_state_env(tenant_info.get("market_served"))

    if not jur_id or not state_env:
        return {"status": "error", "error_message": "Backend could not automatically resolve jurisdiction."}

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
    """Return tenant and selected-property values already attached to this run."""

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


from agno.run.agent import RunInput
from agno.session.agent import AgentSession


def inject_gridics_context_pre_hook(run_input: RunInput, session: AgentSession, **kwargs) -> None:
    """Pre-hook to fetch Gridics data and inject it straight into the LLM's prompt."""

    run_context = kwargs.get("run_context") or session
    context_kwargs = dict(kwargs)
    context_kwargs.pop("run_context", None)
    context = get_active_tenant_context(run_context=run_context, **context_kwargs)
    property_data = context.get("property")

    if not property_data or "latitude" not in property_data or "longitude" not in property_data:
        return

    lat = property_data["latitude"]
    lng = property_data["longitude"]
    state_env = context.get("state_env")
    jur_id = context.get("jurisdiction_id")

    if not state_env or not jur_id:
        print("[pre_hook] Missing state_env or jurisdiction_id. Skipping injection.")
        return

    try:
        print(f"[pre_hook] Fetching Gridics context for {lat}, {lng}...")
        gridics_facts = get_property_context(
            lat=lat,
            lng=lng,
            state_env=state_env,
            jurisdiction_id=jur_id,
        )

        injection = f"\n\n### SYSTEM INJECTED PROPERTY FACTS ###\n{gridics_facts}\n####################################\n"

        if hasattr(run_input, "message") and isinstance(run_input.message, str):
            run_input.message += injection
        elif hasattr(run_input, "input_content") and isinstance(run_input.input_content, str):
            run_input.input_content += injection
    except Exception as exc:
        print(f"[pre_hook] Failed to fetch or inject Gridics data: {exc}")


def _apply_customer_zoning_model_pre_hook(agent: Agent, run_context: Any = None, metadata: Any = None, **kwargs: Any) -> None:
    resolved_model_id = _resolve_customer_zoning_model_id(run_context=run_context, metadata=metadata, **kwargs)
    current_model_id = getattr(getattr(agent, "model", None), "id", None)
    if current_model_id == resolved_model_id:
        return

    print(f"constructing customer zoning agent with model {resolved_model_id}")
    agent.model = Gemini(id=resolved_model_id, api_key=_GEMINI_API_KEY)


def build_customer_zoning_agent() -> Agent:
    print(f"constructing customer zoning agent with model {CUSTOMER_ZONING_AGENT_MODEL_ID}")
    return Agent(
        id="customer-zoning-agent",
        name="Expert Zoning Assistant",
        description="Grounded zoning assistant that answers property-specific questions using Gridics data and zoning code search.",
        model=Gemini(id=CUSTOMER_ZONING_AGENT_MODEL_ID, api_key=_GEMINI_API_KEY),
        tools=[search_zoning_code],
        pre_hooks=[_apply_customer_zoning_model_pre_hook, inject_gridics_context_pre_hook],
        db=AGNO_DB,
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
            "You are an Expert Zoning Assistant. Answer the user's zoning questions using the context provided.",
            "Keep the conversation strictly within zoning, urban planning, and land use scope.",
            "",
            "### BOUNDARIES & DISCLAIMERS (CRITICAL)",
            "- Do not present your answer as legal advice, a permit approval, or a final determination by the jurisdiction.",
            "- Do not invent zoning districts, parcel facts, code standards, or source URLs that were not provided by your tools or injected context.",
            "- If the request goes beyond zoning into other topics (e.g., engineering, valuation), answer ONLY the zoning-related portion.",
            "",
            "### CRITICAL: ACTIVE CONTEXT",
            "Your backend has automatically injected the required context into your prompt below:",
            "- CLIENT ID: {client_id}",
            "- ACTIVE PROPERTY: {property}",
            "If the `ACTIVE PROPERTY` contains coordinates (latitude/longitude), you MUST treat the request as a PROPERTY-SPECIFIC QUESTION.",
            "",
            "### SOURCE OF TRUTH HIERARCHY",
            "1. **PRIMARY - GRIDICS FACTS:** If your prompt contains a 'SYSTEM INJECTED PROPERTY FACTS' block, you MUST use those specific pre-calculated numbers (e.g., maximum density, maximum height) as your absolute source of truth. Do not recalculate these base limits.",
            "   - IF the injected Gridics Facts completely answer the user's question, answer immediately without searching the code.",
            "2. **STATE LAW PREEMPTION (LIVE LOCAL ACT):** The Florida Live Local Act (SB 102) preempts local zoning codes. The maximum density allowed under the Live Local Act is 1,000 Dwelling Units per acre.",
            "   - If the user asks about 'Live Local', 'SB 102', or state density bonuses, DO NOT search the local zoning code for density rules.",
            "   - YOU MUST calculate the allowed units yourself using the injected Gridics facts: Multiply the `lot_area_acres` by 1000 (or divide `lot_area_sqft` by 43,560 and multiply by 1000).",
            "3. **SECONDARY - ZONING CODE (EXCEPTIONS & CONDITIONS):** You MUST use the `search_zoning_code` tool IF:",
            "   - The user asks about a specific local constraint or condition (e.g., 'small lot', 'corner lot').",
            "   - The user asks for policy rules, definitions, or local overlays not explicitly calculated in the Gridics Facts.",
            "",
            "### TOOL SEARCH STRATEGY (MANDATORY)",
            "- **Translate to Zoning Terminology:** Users often use colloquial terms (e.g., 'small lot', 'narrow'). Do NOT search for these exact phrases. Translate them into formal zoning concepts (e.g., 'lot area', 'lot width', 'exceptions') and use the exact dimensions from the injected Gridics facts (e.g., 'lot area under 10000 sq ft T6').",
            "- **Base Query:** Include the Zoning District in your initial search query.",
            "- **Zone Abstraction:** Zoning codes group text rules by base category. If specific district searches fail, drop the suffixes (e.g., use 'T6' instead of 'T6-48B-O').",
            "- **Cross-Reference Chasing:** Zoning codes are full of cross-references. If a search result tells you to 'See Table 4', 'Refer to Article 6', or points to another section, you MUST NOT stop and tell the user to read it. You MUST call the `search_zoning_code` tool a second time, specifically querying for that referenced table or section.",
            "- **Vector Search Fallback:** If your initial search does not return a specific limit, call the tool a second time using a broader query.",
            "- **NO HESITATION:** Do NOT ask the user for clarifying details before searching the code. Search first, then summarize.",
            "### EVIDENCE AND UNCERTAINTY",
            "- Do not overstate certainty. Distinguish clearly between what is confirmed, what is likely, and what still needs verification.",
            "- If a conclusion depends on missing parcel facts, missing code sections, or discretionary review (e.g., 'Warrant or Exception'), state that plainly.",
            "- Separate direct conclusions from assumptions.",
            "",
            "### FINAL ANSWER FORMATTING & HYPERLINKS",
            "Your final response must be highly readable, practical, and decision-oriented.",
            "1. DIRECT ANSWER: For yes/no questions, lead with the short answer. Start with a clear, concise sentence answering the user's core question.",
            "2. PLAIN ENGLISH: Translate zoning language into plain English without losing the legal meaning.",
            "3. PROPERTY CONTEXT: If a property is selected, briefly state its Zoning District using bullet points.",
            "4. STRUCTURED RULES: Use bullet points to list specific regulations. Bold the key terms.",
            "5. HYPERLINK CITATIONS: You MUST explicitly cite the source of your information immediately at the end of the sentence or bullet point.",
            "   - For injected Gridics facts, use plain text: `(reference: Gridics property data)`.",
            "   - For code rules, the `search_zoning_code` tool returns a `section_url` (or `page_url`) alongside the text. You MUST extract this URL and format the citation as a markdown link with a short friendly label.",
            "   - Use the exact style: `([Section 3.14.1](URL))` or `([Illustration 5.6](URL))`.",
            "   - Never emit raw HTML `<a>` tags for citations.",
            "",
            "Example of a perfect response layout:",
            "Yes, based on the property's size and zoning, you can build a maximum of 25 units.",
            "",
            "**Property Context:**",
            "- The property is located in the **T5-O** zoning district (reference: Gridics property data).",
            "",
            "**Density Regulations:**",
            "- **Maximum Units:** The specific parcel allows for a maximum of **25 units** (reference: Gridics property data).",
            "- **Base Rule:** The general code allows a maximum density of 150 Dwelling Units per acre in the T5 zone ([Section 5.2.3 Building Function & Density](https://codehub.gridics.com/...))."
        ],
    )


def build_zoning_assistant_agent() -> Agent:
    warnings.warn(
        "build_zoning_assistant_agent is deprecated; use build_customer_zoning_agent instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return build_customer_zoning_agent()


def build_code_researcher_agent(*, model_id: str | None = None) -> Agent:
    warnings.warn(
        "build_code_researcher_agent is deprecated; the customer zoning assistant now runs as a single agent.",
        DeprecationWarning,
        stacklevel=2,
    )
    return build_customer_zoning_agent()


def build_code_researcher_members(*, run_context: Any = None, metadata: Any = None, **kwargs: Any) -> list[Agent]:
    warnings.warn(
        "build_code_researcher_members is deprecated; the customer zoning assistant no longer uses member agents.",
        DeprecationWarning,
        stacklevel=2,
    )
    return [build_customer_zoning_agent()]


def build_code_researcher_members_cache_key(*, run_context: Any = None, metadata: Any = None, **kwargs: Any) -> str:
    warnings.warn(
        "build_code_researcher_members_cache_key is deprecated; the customer zoning assistant no longer uses member caches.",
        DeprecationWarning,
        stacklevel=2,
    )
    return "deprecated"


def build_customer_zoning_team() -> Agent:
    warnings.warn(
        "build_customer_zoning_team is deprecated; use build_customer_zoning_agent instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return build_customer_zoning_agent()
