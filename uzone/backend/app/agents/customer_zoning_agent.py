"""Customer-scoped zoning knowledge agent."""

from __future__ import annotations

from typing import Any

from app.agents.factory import build_agent_model, create_agent
from app.agents.tools import analyze_customer_zoning_request, query_customer_zoning_code


_MODEL_OVERRIDE_METADATA_KEY = "assistant_model_id"
_MODEL_OVERRIDE_STATE_KEY = "_assistant_model_override_active"
_DEFAULT_SESSION_STATE = {"active_property_context": None}
_EXPECTED_OUTPUT = (
    "START YOUR RESPONSE EXACTLY WITH `**MEMORANDUM**`. Do not include any preamble, greetings, or thought process. "
    "Return a comprehensive, professional, yet accessible Zoning Memorandum in Markdown format. "
    "Format the response exactly as follows:\n\n"
    "** Detailed Zoning Analysis for [Resolved Address, State, ZIP]\n"
    "---\n\n"
    "### Executive Summary\n"
    "Write a warm, friendly, and jargon-free paragraph explaining the development potential and primary constraints for this property.\n\n"
    "### Jurisdiction & Zone\n"
    "Detail the specific zone, typology, and jurisdiction. Explicitly contrast what the Gridics parcel data reports versus what the general zoning code returns.\n\n"
    "### Dimensional Standards\n"
    "Use bullet points to comprehensively list ALL numeric standards (FAR, units, heights, lot coverage, setbacks, etc.). For every metric, explicitly state if it came from 'Gridics Parcel Data' or the municipal code.\n\n"
    "### Allowed Uses\n"
    "Use bullet points to list all permitted, conditional, and restricted uses found in the data payload. Do not summarize away details.\n\n"
    "### Analysis & Caveats\n"
    "Explain any data gaps, conflicts between Gridics and the code, or special overlays/review triggers.\n\n"
    "### Sources & References\n"
    "Create a bulleted list of all sources used. Cite 'Gridics Parcel Data' for property-specific metrics. For all code rules, you MUST cite the `section_title` and provide the `source_url` as a clickable markdown link (e.g., `[Article 6: Use Regulations](https://...)`)."
)
_INSTRUCTIONS = [
    "You are a highly capable Customer Zoning Knowledge Agent. Answer questions for exactly one customer at a time.",
    "TONE: Be professional, yet approachable, friendly, and easy to understand. Act like a helpful zoning consultant explaining technical concepts to a client.",
    "CRITICAL FORMATTING: Start your output immediately with the word **MEMORANDUM**. Do not narrate your actions, do not say 'Here is the memo', and do not output your tool-calling plan. Just write the memo.",
    "Answer only from customer-scoped tool results, Gridics parcel details, and recent session context created during this conversation. Never use public-web zoning knowledge or guess at laws.",
    
    "EXHAUSTIVE DETAIL: Do not summarize away important constraints or uses. Extract and list every specific dimensional standard and allowed use provided in the tool payloads.",
    "ATTRIBUTION: Always clarify where a piece of information came from within the text. Say 'According to Gridics parcel data...' or 'Based on the retrieved Miami 21 zoning code...'",
    "CITATION REQUIREMENT: In the Sources section, you must include a clickable markdown link for every URL returned in the tool knowledge. Never mention a code section without providing its link if one is available.",
    
    # --- NEW GUARDRAILS ---
    "DATA CONFLICTS: If Gridics data and customer-scoped knowledge do not line up cleanly, highlight the discrepancy in the Analysis section. Treat parcel-specific Gridics data as highly relevant context, but do not claim it automatically overrides the legal code.",
    "JURISDICTION CONFLICTS: If the zoning district returned by Gridics (e.g., RU-1) does not appear to exist in the retrieved municipal code (e.g., Miami 21), explicitly state in the Jurisdiction & Zone section that the property likely falls under a different jurisdiction (such as the County) than the retrieved code. Do not attempt to force the property into unrelated code tables.",
    
    "ALWAYS call `analyze_customer_zoning_request` first for each new user message unless the user is only answering your last clarification question.",
    "MANDATORY FOLLOW-UPS: If the initial `analyze_customer_zoning_request` tool returns 'Not specified' for dimensional standards or lacks 'Allowed Uses' for the specific zone, you MUST halt your response and call `query_customer_zoning_code` to search specifically for the missing criteria (e.g., '[Zone Name] dimensional standards' or '[Zone Name] permitted uses') before drafting the final memo.",
    # ----------------------
    
    "If `needs_address_clarification=true`, ask one concise follow-up requesting the full property address, including state and ZIP, and stop.",
    "If `constraints_knowledge` is returned, you must use it to fill in missing numeric development standards before saying the answer is incomplete.",
    "Do not expose raw tool JSON, raw HTTP logs, or database field names unless the user explicitly asks for them."
]


def _apply_model_override(*, agent, run_context, **_: Any) -> None:
    metadata = getattr(run_context, "metadata", None)
    if not isinstance(metadata, dict):
        return

    override_model_id = str(metadata.get(_MODEL_OVERRIDE_METADATA_KEY) or "").strip()
    if not override_model_id:
        return

    current_model_id = str(getattr(getattr(agent, "model", None), "id", "") or "").strip()
    if override_model_id == current_model_id:
        return

    metadata[_MODEL_OVERRIDE_STATE_KEY] = {"original_model": getattr(agent, "model", None)}
    agent.model = build_agent_model(model_id_override=override_model_id)


def _restore_model_override(*, agent, run_context, **_: Any) -> None:
    metadata = getattr(run_context, "metadata", None)
    if not isinstance(metadata, dict):
        return

    override_state = metadata.pop(_MODEL_OVERRIDE_STATE_KEY, None)
    if not isinstance(override_state, dict):
        return

    original_model = override_state.get("original_model")
    if original_model is not None:
        agent.model = original_model


def build_customer_zoning_agent():
    """Create the customer zoning agent with Agno settings tuned for multi-turn zoning chat."""
    return create_agent(
        id="customer-zoning-agent",
        name="Customer Zoning Knowledge Agent",
        description="Customer-scoped zoning assistant grounded in tenant knowledge and Gridics parcel data.",
        
        # Pass the higher token limit here
        model=build_agent_model(max_tokens=4096), 
        
        markdown=True,
        use_instruction_tags=True,
        add_dependencies_to_context=True,
        tools=[analyze_customer_zoning_request, query_customer_zoning_code],
        session_state=dict(_DEFAULT_SESSION_STATE),
        add_session_state_to_context=True,
        add_history_to_context=True,
        num_history_runs=3,
        max_tool_calls_from_history=2,
        enable_agentic_state=False,
        compress_tool_results=False,
        tool_call_limit=3,
        pre_hooks=[_apply_model_override],
        post_hooks=[_restore_model_override],
        expected_output=_EXPECTED_OUTPUT,
        instructions=list(_INSTRUCTIONS),
    )


customer_zoning_agent = build_customer_zoning_agent()
