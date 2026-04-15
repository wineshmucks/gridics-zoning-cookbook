"""Customer-scoped multi-agent zoning team."""

from __future__ import annotations
import types
from typing import Any
from agno.team import Team
from sqlalchemy import select

from app.agents.assistant_defaults import (
    ASSISTANT_TARGET_IDS,
    CODE_DEFAULT_ASSISTANT_MODEL_TARGETS,
)
from app.agents.factory import build_agent_model, create_agent, get_model_trace
from app.agents.tools import analyze_customer_zoning_request, query_customer_zoning_code
from app.db.models import TenantClient
from app.db.session import SessionLocal
from app.services.embed_service import decode_embed_session_token
from app.services.assistant_telemetry_service import record_assistant_run_telemetry
from app.services.platform_settings_service import get_platform_assistant_settings_json
from app.services.tenant_service import (
    get_tenant_assistant_agent_prompts,
    get_tenant_assistant_settings,
    merge_assistant_agent_prompts,
    merge_assistant_model_targets,
    merge_assistant_provider_keys,
)

_MODEL_OVERRIDE_METADATA_KEY = "assistant_model_id"
_MODEL_OVERRIDE_STATE_KEY = "_assistant_model_override_active"
_TENANT_ASSISTANT_CONFIG_STATE_KEY = "_tenant_assistant_config_active"
_DEFAULT_SESSION_STATE = {"active_property_context": None, "jurisdiction_lock": None}


def _first_nonempty_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
    return None


def _get_run_client_id(run_context: Any) -> str | None:
    metadata = getattr(run_context, "metadata", None)
    if isinstance(metadata, dict):
        embed_token = str(metadata.get("embed_token") or "").strip()
        if embed_token:
            try:
                payload = decode_embed_session_token(embed_token)
            except Exception:
                payload = None

            if isinstance(payload, dict):
                token_client_id = str(payload.get("client_id") or "").strip()
                if token_client_id:
                    return token_client_id

    dependencies = getattr(run_context, "dependencies", None)
    if not isinstance(dependencies, dict):
        return None
    client_id = dependencies.get("client_id")
    return client_id.strip() if isinstance(client_id, str) and client_id.strip() else None


def _get_run_conversation_id(run_context: Any, telemetry_payload: Any = None) -> str | None:
    metadata = getattr(run_context, "metadata", None)
    metadata_conversation_id = None
    metadata_session_id = None
    metadata_thread_id = None
    if isinstance(metadata, dict):
        metadata_conversation_id = metadata.get("conversation_id")
        metadata_session_id = metadata.get("session_id")
        metadata_thread_id = metadata.get("thread_id")

    payload_conversation_id = None
    payload_session_id = None
    payload_thread_id = None
    if isinstance(telemetry_payload, dict):
        payload_conversation_id = telemetry_payload.get("conversation_id")
        payload_session_id = telemetry_payload.get("session_id")
        payload_thread_id = telemetry_payload.get("thread_id")
    else:
        payload_conversation_id = getattr(telemetry_payload, "conversation_id", None)
        payload_session_id = getattr(telemetry_payload, "session_id", None)
        payload_thread_id = getattr(telemetry_payload, "thread_id", None)

    return _first_nonempty_string(
        metadata_conversation_id,
        metadata_session_id,
        metadata_thread_id,
        getattr(run_context, "conversation_id", None),
        getattr(run_context, "session_id", None),
        getattr(run_context, "thread_id", None),
        payload_conversation_id,
        payload_session_id,
        payload_thread_id,
    )


def _build_hook_context(
    *,
    run_context: Any = None,
    metadata: dict[str, Any] | None = None,
    dependencies: dict[str, Any] | None = None,
    session_state: dict[str, Any] | None = None,
    session: Any = None,
    user_id: str | None = None,
    debug_mode: bool | None = None,
) -> Any:
    if run_context is not None:
        return run_context

    context = types.SimpleNamespace()
    context.metadata = metadata if isinstance(metadata, dict) else {}
    context.dependencies = dependencies if isinstance(dependencies, dict) else {}
    context.session_state = session_state if isinstance(session_state, dict) else {}
    context.session_id = getattr(session, "id", None)
    context.user_id = user_id
    context.debug_mode = debug_mode
    return context


def _load_tenant_assistant_config(
    client_id: str,
) -> tuple[dict[str, str | None], dict[str, dict[str, str | None]], dict[str, str]]:
    with SessionLocal() as db:
        platform_settings_json = get_platform_assistant_settings_json(db)
        platform_provider_keys, platform_model_targets = get_tenant_assistant_settings(platform_settings_json)
        platform_agent_prompts = get_tenant_assistant_agent_prompts(platform_settings_json)
        tenant_client = db.scalar(select(TenantClient).where(TenantClient.client_id == client_id))
        if tenant_client is None:
            return platform_provider_keys, platform_model_targets, platform_agent_prompts
        provider_keys, model_targets = get_tenant_assistant_settings(tenant_client.settings_json)
        agent_prompts = get_tenant_assistant_agent_prompts(tenant_client.settings_json)
        return (
            merge_assistant_provider_keys(platform_provider_keys, provider_keys),
            merge_assistant_model_targets(platform_model_targets, model_targets),
            merge_assistant_agent_prompts(platform_agent_prompts, agent_prompts),
        )


def _target_members(target: Any) -> list[Any]:
    members = getattr(target, "members", None)
    return list(members) if isinstance(members, list) else []


def _resolve_target_config(
    target_id: str,
    model_targets: dict[str, dict[str, str | None]],
) -> dict[str, str | None]:
    code_default = CODE_DEFAULT_ASSISTANT_MODEL_TARGETS.get(target_id, {})
    saved_target = model_targets.get(target_id) or {}
    provider = str(saved_target.get("provider") or code_default.get("provider") or "").strip().lower()
    model_id = str(saved_target.get("model_id") or code_default.get("model_id") or "").strip()
    base_url = str(saved_target.get("base_url") or code_default.get("base_url") or "").strip() or None
    return {
        "provider": provider or None,
        "model_id": model_id or None,
        "base_url": base_url,
    }


def _apply_tenant_assistant_config(*, agent=None, team=None, run_context, **_: Any) -> None:
    target = _resolve_hook_target(agent=agent, team=team)
    if target is None:
        return

    metadata = getattr(run_context, "metadata", None)
    if not isinstance(metadata, dict):
        return

    client_id = _get_run_client_id(run_context)
    if not client_id:
        raise RuntimeError(
            "Tenant client ID is required for jurisdiction-scoped assistant runs."
        )

    provider_keys, model_targets, agent_prompts = _load_tenant_assistant_config(client_id)
    targets_by_id = {str(getattr(target, "id", "") or ""): target}
    for member in _target_members(target):
        member_id = str(getattr(member, "id", "") or "")
        if member_id:
            targets_by_id[member_id] = member

    original_models: dict[str, Any] = {}
    original_instructions: dict[str, Any] = {}
    applied_targets: dict[str, dict[str, str | None]] = {}

    for target_id in ASSISTANT_TARGET_IDS:
        config = _resolve_target_config(target_id, model_targets)
        provider = str(config.get("provider") or "").strip().lower()
        model_id = str(config.get("model_id") or "").strip()
        base_url = str(config.get("base_url") or "").strip() or None
        resolved_target = targets_by_id.get(target_id)

        if not resolved_target:
            continue
        if not provider or not model_id:
            continue

        api_key = provider_keys.get(provider)
        if not api_key:
            raise RuntimeError(
                f"Assistant setup is incomplete for this jurisdiction. "
                f"Missing API key for provider '{provider}' used by target '{target_id}'."
            )
        original_models[target_id] = getattr(resolved_target, "model", None)
        resolved_target.model = build_agent_model(
            provider=provider,
            model_id=model_id,
            api_key=api_key,
            base_url=base_url,
            allow_env_fallback=False,
        )
        applied_targets[target_id] = {
            "provider": provider,
            "model_id": model_id,
            "base_url": base_url,
        }

    if original_models:
        metadata[_TENANT_ASSISTANT_CONFIG_STATE_KEY] = {
            "original_models": original_models,
            "original_instructions": original_instructions,
            "applied_targets": applied_targets,
            "provider_keys": provider_keys,
        }


def _restore_tenant_assistant_config(*, agent=None, team=None, run_context, **_: Any) -> None:
    target = _resolve_hook_target(agent=agent, team=team)
    if target is None:
        return

    metadata = getattr(run_context, "metadata", None)
    if not isinstance(metadata, dict):
        return

    state = metadata.pop(_TENANT_ASSISTANT_CONFIG_STATE_KEY, None)
    if not isinstance(state, dict):
        return

    original_models = state.get("original_models")
    if not isinstance(original_models, dict):
        original_models = {}
    original_instructions = state.get("original_instructions")
    if not isinstance(original_instructions, dict):
        original_instructions = {}

    targets_by_id = {str(getattr(target, "id", "") or ""): target}
    for member in _target_members(target):
        member_id = str(getattr(member, "id", "") or "")
        if member_id:
            targets_by_id[member_id] = member

    for target_id, original_model in original_models.items():
        resolved_target = targets_by_id.get(target_id)
        if resolved_target is not None:
            resolved_target.model = original_model

    for target_id, original_prompt in original_instructions.items():
        resolved_target = targets_by_id.get(target_id)
        if resolved_target is not None:
            resolved_target.instructions = original_prompt

# --- HOOKS ---
def _resolve_hook_target(*, agent=None, team=None):
    return team if team is not None else agent

def _apply_model_override(*, agent=None, team=None, run_context, **_: Any) -> None:
    target = _resolve_hook_target(agent=agent, team=team)
    if target is None: return
    metadata = getattr(run_context, "metadata", None)
    if not isinstance(metadata, dict): return
    override_model_id = str(metadata.get(_MODEL_OVERRIDE_METADATA_KEY) or "").strip()
    if not override_model_id: return
    current_model_id = str(getattr(getattr(target, "model", None), "id", "") or "").strip()
    if override_model_id == current_model_id: return
    tenant_state = metadata.get(_TENANT_ASSISTANT_CONFIG_STATE_KEY)
    if not isinstance(tenant_state, dict):
        raise RuntimeError(
            "Model override requires jurisdiction assistant setup and cannot use environment keys."
        )
    applied_targets = tenant_state.get("applied_targets")
    provider_keys = tenant_state.get("provider_keys")
    if not isinstance(applied_targets, dict) or not isinstance(provider_keys, dict):
        raise RuntimeError(
            "Model override requires jurisdiction assistant setup and cannot use environment keys."
        )
    target_id = str(getattr(target, "id", "") or "").strip()
    target_config = applied_targets.get(target_id)
    if not isinstance(target_config, dict):
        raise RuntimeError(
            f"Model override is not available because target '{target_id}' is not configured for this jurisdiction."
        )
    provider = str(target_config.get("provider") or "").strip().lower()
    base_url = str(target_config.get("base_url") or "").strip() or None
    api_key = provider_keys.get(provider)
    if not provider or not api_key:
        raise RuntimeError(
            f"Model override is not available because provider '{provider or 'unknown'}' has no jurisdiction API key."
        )
    metadata[_MODEL_OVERRIDE_STATE_KEY] = {"original_model": getattr(target, "model", None)}
    target.model = build_agent_model(
        provider=provider,
        model_id=override_model_id,
        api_key=api_key,
        base_url=base_url,
        allow_env_fallback=False,
    )

def _restore_model_override(*, agent=None, team=None, run_context, **_: Any) -> None:
    target = _resolve_hook_target(agent=agent, team=team)
    if target is None: return
    metadata = getattr(run_context, "metadata", None)
    if not isinstance(metadata, dict): return
    override_state = metadata.pop(_MODEL_OVERRIDE_STATE_KEY, None)
    if not isinstance(override_state, dict): return
    target.model = override_state.get("original_model")


def _record_run_telemetry(
    *,
    agent=None,
    team=None,
    run_output=None,
    run_context=None,
    session=None,
    session_state=None,
    dependencies=None,
    metadata=None,
    user_id=None,
    debug_mode=None,
    response=None,
    result=None,
    **_: Any,
) -> None:
    target = _resolve_hook_target(agent=agent, team=team)
    if target is None:
        return

    hook_context = _build_hook_context(
        run_context=run_context,
        metadata=metadata,
        dependencies=dependencies,
        session_state=session_state,
        session=session,
        user_id=user_id,
        debug_mode=debug_mode,
    )
    metadata = getattr(hook_context, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}

    client_id = _get_run_client_id(hook_context)
    telemetry_payload = run_output if run_output is not None else response if response is not None else result
    payload = {
        "run_scope": "team" if team is not None else "agent",
        "agent_id": str(getattr(target, "id", "") or "") or None,
        "conversation_id": _get_run_conversation_id(hook_context, telemetry_payload),
        "message_id": _first_nonempty_string(metadata.get("message_id"), getattr(hook_context, "message_id", None)),
        "run_id": _first_nonempty_string(metadata.get("run_id"), getattr(hook_context, "run_id", None)),
        "session_id": _first_nonempty_string(
            metadata.get("session_id"),
            getattr(hook_context, "session_id", None),
            getattr(telemetry_payload, "session_id", None) if telemetry_payload is not None else None,
        ),
        "model_trace": get_model_trace(getattr(target, "model", None)),
        "metrics": getattr(telemetry_payload, "metrics", None) if telemetry_payload is not None else None,
        "run_output": telemetry_payload,
    }
    if isinstance(telemetry_payload, dict):
        payload["metrics"] = telemetry_payload.get("metrics") or telemetry_payload.get("usage") or telemetry_payload.get("usage_metrics")

    record_assistant_run_telemetry(client_id=client_id, payload=payload)


# --- 1. PARCEL DATA AGENT (API Specialist) ---
parcel_data_agent = create_agent(
    id="parcel-data-agent",
    name="Parcel Data Agent",
    role="Fetch pre-compressed property data from the Gridics API.",
    # Since this agent just passes a string now, you can use a smaller, faster model if desired!
    model=build_agent_model(provider="gemini", model_id="gemini-2.5-flash-lite", allow_missing_api_key=True),
    tools=[analyze_customer_zoning_request],
    post_hooks=[_record_run_telemetry],
    instructions=[
        "Your ONLY job is to call `analyze_customer_zoning_request` for the requested address.",
        "If the delegated task includes a tenant client ID, you MUST pass that exact value as `client_id` in the tool call.",
        "The tool will return a cleanly formatted Markdown summary of the property. Pass this exact summary back to the Lead Agent.",
        "Do NOT alter the numbers. Do NOT write the final analysis memo."
    ],
)

# --- 2. CODE RESEARCHER AGENT (Knowledge Specialist) ---
code_researcher_agent = create_agent(
    id="code-researcher-agent",
    name="Code Researcher Agent",
    role="Query the customer zoning code knowledge base for legal text and citations.",
    model=build_agent_model(provider="gemini", model_id="gemini-2.5-flash", allow_missing_api_key=True),
    tools=[query_customer_zoning_code],
    post_hooks=[_record_run_telemetry],
    instructions=[
        "You are the Zoning Code Legal Researcher.",
        "You may receive specific property information (Zone Name and Overlays) from the Lead Agent, OR general zoning questions (e.g., permitted uses, administrative procedures, definitions).",
        "Your ONLY job is to call `query_customer_zoning_code` to find the relevant legal text, definitions, and rules based on the request.",
        "If the delegated task includes a tenant client ID, you MUST pass that exact value as `client_id` in every tool call.",
        "1. For address-specific queries: Query for the exact Zone Name's dimensional standards and specific overlay rules.",
        "2. For general queries: Query the code for general use tables, definitions (e.g., Special Plan/PUD), or procedural requirements.",
        "Return the exact text, conditions, `section_title`, `source_url`, and `section_url` for everything you find. Do not write the final analysis memo."
    ],
)

# --- 3. LEAD SYNTHESIZER AGENT (The Manager) ---
_EXPECTED_OUTPUT = (
    "Do not include any preamble, narrations of your tool calls, or thought process. "
    "Return a comprehensive, professional, yet conversational Zoning Analysis in Markdown format. "
    "Format the response exactly matching this structure and tone:\n\n"
    "The property at **[Resolved Address]** is a **[LotAreaAcres]**-acre parcel located in the **[Zone Name]** zoning district. "
    "[Write 1-2 sentences explaining what this designation means at a high level based on the code research].\n\n"
    "### Property Snapshot (Gridics Data)\n"
    "| Metric | Gridics Allowance |\n"
    "| :--- | :--- |\n"
    "| **Lot Size** | [LotAreaFeet] sq ft ([LotAreaAcres] acres) |\n"
    "| **Max Density** | [DensityUnits] Units |\n"
    "| **Max Height** | [TotalBuidingHeight] Stories |\n"
    "| **Max Building Area** | [MaxBuildingAreaAllowed] sq ft |\n"
    "| **Lot Coverage** | [EffectiveLotCoverage]% |\n\n"
    "### Permitted Uses in [Zone Name]\n"
    "[Write a brief introductory sentence explaining the flexibility of the zone based on the code.]\n"
    "* **[Use Category 1] (e.g., Lodging):** [Explain if it is permitted By Right, Warrant, or Exception]. *(Code confirmation: [Code Section Title](url))*.\n"
    "* **[Use Category 2] (e.g., Food Service):** [Explain the allowance and any operational footprint conditions]. *(Code: [Code Section Title](url))*.\n"
    "* **[Use Category 3]:** [Explain the allowance and context]. *(Code: [Code Section Title](url))*.\n\n"
    "### Development Capacity and Dimensional Standards\n"
    "While the Gridics snapshot provides the base allowances for this specific lot, here are the physical constraints and potential bonuses based on the municipal code:\n"
    "* **Height & Floor Area:** The code confirms a base height limit and FLR. [Explain how this can be increased with public benefits or TOD bonuses, explicitly comparing it to the Gridics Snapshot numbers. Cite the code: ([Section Title](url))].\n"
    "* **Setbacks & Massing:** [List detailed setback rules for podium/tower] ([Section Title](url)).\n\n"
    "### Site Constraints & Overlays\n"
    "[List the specific overlays found in the Gridics data and explain exactly what the zoning code says about them using inline links].\n\n"
    "### Analysis & Caveats\n"
    "[Explain any data gaps, or explicitly detail any conflicts found between the Gridics parcel data and the retrieved code].\n\n"
    "---\n"
    "**[Conversational Follow-Up Question]** (e.g., 'Would you like me to look deeper into the specific parking reductions allowed for this Transit Corridor?' or 'Do you want to see the specific requirements for the Public Benefit bonus?')"
)

def build_customer_zoning_team():
    """Create the Lead Agent that manages the sub-agents."""
    return Team(
        id="customer-zoning-agent",
        name="Customer Zoning Lead Agent",
        description="Lead zoning consultant orchestrating data extraction and code research to write analysis.",
        # UPGRADED MODEL: Changed from flash-lite to flash for better manager-level orchestration and logic
        model=build_agent_model(provider="gemini", model_id="gemini-2.5-flash", allow_missing_api_key=True),

        members=[parcel_data_agent, code_researcher_agent],
        tools=[analyze_customer_zoning_request, query_customer_zoning_code],
        markdown=True,
        use_instruction_tags=True,
        add_dependencies_to_context=True,
        session_state=dict(_DEFAULT_SESSION_STATE),
        add_session_state_to_context=True,
        add_team_history_to_members=True,
        num_team_history_runs=3,
        enable_agentic_state=False,

        pre_hooks=[_apply_tenant_assistant_config, _apply_model_override],
        post_hooks=[_record_run_telemetry, _restore_model_override, _restore_tenant_assistant_config],
        # removed expected_output parameter to allow for dynamic formatting
        instructions=[
            "You are the Lead Customer Zoning Knowledge Agent.",
            "TONE: Act like a highly knowledgeable, friendly zoning consultant speaking directly to a client.",
            
            "--- ROUTING AND DELEGATION LOGIC ---",
            "Assess the user's prompt to determine if it is ADDRESS-SPECIFIC or a GENERAL KNOWLEDGE query.",
            
            "SCENARIO A: ADDRESS-SPECIFIC QUERIES",
            "If the user provides an address or asks about the 'active property', follow this sequence strictly:",
            "1. DELEGATE to the `Parcel Data Agent` to fetch the Gridics parcel data. Wait for its response.",
            "2. Review the data. If the Parcel Data Agent reports it cannot find the property, explain that the parcel could not be resolved and ask the user to confirm the address.",
            "3. If successful, identify the exact Zone Name and Overlays.",
            "4. DELEGATE to the `Code Researcher Agent` to find the legal text for that exact Zone Name and those Overlays. Wait for its response.",
            "5. SYNTHESIZE the final response based on the formatting rules below.",
            "Note: If `analyze_customer_zoning_request` returns `needs_confirmation: true`, reply ONLY with the exact message asking the user to confirm the address and WAIT.",
            "While that pending confirmation state is active, interpret the next user reply against that state instead of treating it like a brand-new zoning question.",
            "If the user then replies with a short affirmative like 'yes continue', 'confirm', 'yes', 'continue', or 'go ahead', treat that as confirmation of the pending address and continue with the resolved parcel instead of asking again.",

            "SCENARIO B: GENERAL KNOWLEDGE QUERIES",
            "If the user asks a general question (e.g., 'What zones allow a mechanic shop?', 'Differences between T5-R and T5-O?', 'How to apply for a PUD?'):",
            "1. DO NOT call the Parcel Data Agent.",
            "2. DELEGATE directly to the `Code Researcher Agent` to find the relevant code sections, use tables, or procedural rules.",
            "3. SYNTHESIZE the final response based on the Code Researcher's findings.",

            "--- OUTPUT FORMATTING ---",
            "NEVER narrate your actions to the user (e.g., do not say 'I am checking the data'). Cite your code sources INLINE using clickable markdown links such as `([Article 5](url))`. Prefer `section_url` when available; otherwise use `source_url`.",

            "Format 1: Specific/Targeted Questions (e.g., 'How high can I build a fence at [Address]?' or 'Where can I open a bar?')",
            "Answer the specific question directly and thoroughly using the active context or code findings. DO NOT generate a full property overview or tables.",
            
            "Format 2: General Property Overview (e.g., 'What can I build at [Address]?')",
            "Return a comprehensive Zoning Analysis using EXACTLY this markdown structure:",
            "The property at **[Resolved Address]** is a **[LotAreaAcres]**-acre parcel located in the **[Zone Name]** zoning district. [1-2 sentences explaining designation].",
            "### Property Snapshot (Gridics Data)",
            "| Metric | Gridics Allowance |",
            "| :--- | :--- |",
            "| **Lot Size** | [LotAreaFeet] sq ft ([LotAreaAcres] acres) |",
            "| **Max Density** | [DensityUnits] Units |",
            "| **Max Height** | [TotalBuidingHeight] Stories |",
            "| **Max Building Area** | [MaxBuildingAreaAllowed] sq ft |",
            "| **Lot Coverage** | [EffectiveLotCoverage]% |",
            "### Permitted Uses in [Zone Name]",
            "[Bullet points for common use categories based on code].",
            "### Development Capacity and Dimensional Standards",
            "While the Gridics snapshot provides the base allowances, here are the physical constraints and potential bonuses based on the municipal code: [Explain height, FAR, setbacks, and explicitly compare Gridics data with Code bonuses].",
            "### Site Constraints & Overlays",
            "[Explain overlay rules from code].",
            "### Analysis & Caveats",
            "[Explain data gaps or conflicts].",
            
            "---\n",
            "End every response with a single, highly relevant follow-up question based on the context of the user's query."
        ],
    )

customer_zoning_team = build_customer_zoning_team()
customer_zoning_agent = customer_zoning_team
