"""Customer-scoped multi-agent zoning team."""

from __future__ import annotations
from typing import Any
from agno.team import Team
from sqlalchemy import select

from app.agents.factory import build_agent_model, create_agent, get_model_trace
from app.agents.tools import analyze_customer_zoning_request, query_customer_zoning_code
from app.db.models import TenantClient
from app.db.session import SessionLocal
from app.services.embed_service import decode_embed_session_token
from app.services.tenant_service import get_tenant_assistant_settings

_MODEL_OVERRIDE_METADATA_KEY = "assistant_model_id"
_MODEL_OVERRIDE_STATE_KEY = "_assistant_model_override_active"
_TENANT_ASSISTANT_CONFIG_STATE_KEY = "_tenant_assistant_config_active"
_DEFAULT_SESSION_STATE = {"active_property_context": None}
_ASSISTANT_TARGET_IDS = (
    "customer-zoning-agent",
    "parcel-data-agent",
    "code-researcher-agent",
)
_CODE_DEFAULT_TARGET_CONFIG = {
    "customer-zoning-agent": {
        "provider": "gemini",
        # "model_id": "gemini-3.1-flash-lite-preview",
        "model_id": "gemini-flash-lite-latest",
        "base_url": None,
    },
    "parcel-data-agent": {
        "provider": "groq",
        "model_id": "llama-3.1-8b-instant",
        "base_url": None,
    },
    "code-researcher-agent": {
        "provider": "groq",
        "model_id": "llama-3.3-70b-versatile",
        "base_url": None,
    },
}


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


def _load_tenant_assistant_config(client_id: str) -> tuple[dict[str, str | None], dict[str, dict[str, str | None]]]:
    with SessionLocal() as db:
        tenant_client = db.scalar(select(TenantClient).where(TenantClient.client_id == client_id))
        if tenant_client is None:
            return {}, {}
        return get_tenant_assistant_settings(tenant_client.settings_json)


def _target_members(target: Any) -> list[Any]:
    members = getattr(target, "members", None)
    return list(members) if isinstance(members, list) else []


def _resolve_target_config(
    target_id: str,
    model_targets: dict[str, dict[str, str | None]],
) -> dict[str, str | None]:
    code_default = _CODE_DEFAULT_TARGET_CONFIG.get(target_id, {})
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

    provider_keys, model_targets = _load_tenant_assistant_config(client_id)
    targets_by_id = {str(getattr(target, "id", "") or ""): target}
    for member in _target_members(target):
        member_id = str(getattr(member, "id", "") or "")
        if member_id:
            targets_by_id[member_id] = member

    original_models: dict[str, Any] = {}
    applied_targets: dict[str, dict[str, str | None]] = {}

    for target_id in _ASSISTANT_TARGET_IDS:
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
        return

    targets_by_id = {str(getattr(target, "id", "") or ""): target}
    for member in _target_members(target):
        member_id = str(getattr(member, "id", "") or "")
        if member_id:
            targets_by_id[member_id] = member

    for target_id, original_model in original_models.items():
        resolved_target = targets_by_id.get(target_id)
        if resolved_target is not None:
            resolved_target.model = original_model

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


# --- 1. PARCEL DATA AGENT (API Specialist) ---
parcel_data_agent = create_agent(
    id="parcel-data-agent",
    name="Parcel Data Agent",
    role="Fetch pre-compressed property data from the Gridics API.",
    # Since this agent just passes a string now, you can use a smaller, faster model if desired!
    model=build_agent_model(provider="groq", model_id="llama-3.1-8b-instant", allow_missing_api_key=True),
    tools=[analyze_customer_zoning_request],
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
    model=build_agent_model(provider="groq", model_id="llama-3.3-70b-versatile", allow_missing_api_key=True),
    tools=[query_customer_zoning_code],
    instructions=[
        "You are the Zoning Code Legal Researcher.",
        "You will receive a property's Zone Name and Overlays from the Lead Agent.",
        "Your ONLY job is to call `query_customer_zoning_code` to find the legal definitions and rules for those specific items.",
        "If the delegated task includes a tenant client ID, you MUST pass that exact value as `client_id` in every tool call.",
        "1. Query for the exact Zone Name's dimensional standards (e.g., FAR, density, height bonuses).",
        "2. Query for the specific overlay rules provided by the Lead Agent.",
        "Return the exact text, conditions, `section_title`, and `source_url` for everything you find. Do not write the final analysis memo."
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
        model=build_agent_model(provider="gemini", model_id="gemini-flash-lite-latest", allow_missing_api_key=True),

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
        post_hooks=[_restore_model_override, _restore_tenant_assistant_config],
        expected_output=_EXPECTED_OUTPUT,
        instructions=[
            "You are the Lead Customer Zoning Knowledge Agent.",
            "TONE: Act like a highly knowledgeable, friendly zoning consultant speaking directly to a client.",
            
            "--- STRICT DELEGATION SEQUENCE (MANDATORY) ---",
            "You MUST complete these steps in order before responding to the user:",
            "1. DELEGATE to the `Parcel Data Agent` to fetch the Gridics parcel data. Wait for its response.",
            "2. Review the data returned by the Parcel Data Agent. Identify the exact Zone Name and Overlays.",
            "3. DELEGATE to the `Code Researcher Agent` to find the legal text for that exact Zone Name and those Overlays. Wait for its response.",
            "4. Only after receiving BOTH reports, SYNTHESIZE the final analysis.",
            "NEVER output a partial analysis. NEVER narrate your actions to the user (e.g., do not say 'I am checking the data').",
            
            "--- CROSS-REFERENCING & INLINE CITATIONS ---",
            "1. You must populate the 'Property Snapshot' table using the EXACT numeric values returned by the Parcel Data Agent. If the tool says 'Not calculated', put 'Not calculated' in the table.",
            "2. In the 'Development Capacity' section, explicitly compare the Gridics table numbers with the Code Researcher's legal text.",
            "3. Do NOT create a 'Sources' list at the bottom. Cite your code sources INLINE using clickable markdown links: `([Article 5](url))`.",
            
            "--- ACTIVE PROPERTY CONTEXT & FOLLOW-UPS ---",
            "1. When a user provides an address, treat it as the 'Active Property'.",
            "2. If a user asks a follow-up question (e.g., 'Can I build 10 stories?'), do NOT regenerate the entire property overview. Answer the specific question directly and thoroughly using the active context.",
            
            "If the Parcel Data Agent reports it cannot find the property, explain that the parcel could not be resolved and ask the user to confirm the address."
        ],
    )

customer_zoning_team = build_customer_zoning_team()
customer_zoning_agent = customer_zoning_team
