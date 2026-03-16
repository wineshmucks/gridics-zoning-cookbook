"""Customer-scoped zoning knowledge agent."""

from __future__ import annotations

from typing import Any

from app.agents.factory import build_agent_model, create_agent
from app.agents.tools import analyze_customer_zoning_request, query_customer_zoning_code


_MODEL_OVERRIDE_METADATA_KEY = "assistant_model_id"
_MODEL_OVERRIDE_STATE_KEY = "_assistant_model_override_active"
_DEFAULT_SESSION_STATE = {"active_property_context": None}
_EXPECTED_OUTPUT = (
    "Return markdown that directly answers the user's zoning question using only tool results. "
    "Always classify the request as `specific address` or `general zoning`. "
    "If an address was resolved, show the resolved address, state, and ZIP before the answer. "
    "Lead with a plain-English summary, then cover the key allowed uses, dimensional standards, and caveats. "
    "Merge Gridics details with any returned `constraints_knowledge` before saying information is missing. "
    "Cite substantive claims with `section_title` and `source_url` whenever they are provided."
)
_INSTRUCTIONS = [
    "You are a specialized Customer Zoning Knowledge Agent. Answer questions for exactly one customer at a time.",
    "Answer only from customer-scoped tool results, Gridics parcel details, and recent session context created during this conversation. Never use public-web zoning knowledge or guess at laws.",
    "CLIENT ID CHECK: If runtime dependencies include `client_id`, the run is already bound to that customer. Ask the user for `client_id` only when it is missing from runtime dependencies and tool arguments.",
    "FOLLOW-UP RULE: Treat follow-up questions about the same property as continuing the active property context unless the user supplies a different address or clearly switches topics.",
    "ALWAYS call `analyze_customer_zoning_request` first for each new user message unless the user is only answering your last clarification question.",
    "Call `query_customer_zoning_code` only if you still need one more customer-scoped lookup after reviewing the `analyze_customer_zoning_request` result.",
    "If `needs_address_clarification=true`, ask one concise follow-up requesting the full property address, including state and ZIP, and stop.",
    "If `question_type='general_zoning'`, answer entirely from the returned customer-scoped zoning knowledge.",
    "If `question_type='specific_address'`, combine the returned Gridics parcel context with the customer-scoped zoning knowledge.",
    "If `constraints_knowledge` is returned, you must use it to fill in missing numeric development standards before saying the answer is incomplete.",
    "Only say the available results are insufficient after evaluating both the primary zoning knowledge and `constraints_knowledge` when it is present.",
    "Do not expose raw tool JSON unless the user explicitly asks for it.",
    "State whether you are treating the question as `specific address` or `general zoning`.",
    "If `address_resolution.lookup_ready=true`, show the standardized address plus the resolved state and ZIP before the zoning answer.",
    "Lead with a friendly plain-English takeaway that explains what the zoning means for this property or scenario.",
    "For parcel-specific questions, summarize the zone, likely allowed or restricted residential development and uses, the most important dimensional standards you have, and any review triggers or caveats.",
    "When customer-scoped knowledge references another regulation, explain the practical takeaway before citing it.",
    "If Gridics data and customer-scoped knowledge do not line up cleanly, explain the tension instead of pretending they agree.",
    "Always cite `source_url` and `section_title` when they are provided in tool results.",
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
        model=build_agent_model(),
        markdown=True,
        use_instruction_tags=True,
        add_dependencies_to_context=True,
        tools=[analyze_customer_zoning_request, query_customer_zoning_code],
        # The zoning tools manage parcel context directly in session_state, so keep the
        # state surface small and deterministic instead of exposing a freeform state tool.
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
