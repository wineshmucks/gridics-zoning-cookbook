from __future__ import annotations
from typing import Any, Union

from sqlalchemy import select

from agno.agent import Agent
from agno.team import Team
from agno.run.agent import RunOutput
from agno.run import RunContext

from app.agents.factory import build_agent_model, create_agent, get_model_trace
from app.db.models import TenantClient
from app.db.session import SessionLocal
from app.services.embed_service import decode_embed_session_token
from app.services.assistant_telemetry_service import record_assistant_run_telemetry
from app.agents.assistant_defaults import ASSISTANT_TARGET_IDS as DEFAULT_ASSISTANT_TARGET_IDS
from app.agents.assistant_defaults import CODE_DEFAULT_ASSISTANT_MODEL_TARGETS
from app.services.platform_settings_service import get_platform_assistant_settings_json
from app.services.tenant_service import (
    get_tenant_assistant_agent_prompts,
    get_tenant_assistant_settings,
    merge_assistant_agent_prompts,
    merge_assistant_model_targets,
    merge_assistant_provider_keys,
)

ASSISTANT_TARGET_IDS = list(DEFAULT_ASSISTANT_TARGET_IDS)


def _resolve_target_config(target_id: str, model_targets: dict) -> dict:
    """Resolve the assistant target config, forcing Gemini-only runtime models."""
    default_config = CODE_DEFAULT_ASSISTANT_MODEL_TARGETS.get(
        target_id,
        {"provider": "gemini", "model_id": None, "base_url": None},
    )
    raw_config = model_targets.get(target_id) if isinstance(model_targets, dict) else None
    if not isinstance(raw_config, dict):
        return default_config

    provider = str(raw_config.get("provider") or "").strip().lower()
    if provider != "gemini":
        return default_config

    model_id = str(raw_config.get("model_id") or "").strip() or default_config.get("model_id")
    base_url = str(raw_config.get("base_url") or "").strip() or default_config.get("base_url")
    return {
        "provider": "gemini",
        "model_id": model_id,
        "base_url": base_url,
    }

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


def _get_run_client_id(run_context: RunContext) -> str | None:
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


def _get_run_conversation_id(run_context: RunContext) -> str | None:
    metadata = getattr(run_context, "metadata", None)
    metadata_conversation_id = None
    metadata_session_id = None
    metadata_thread_id = None
    
    if isinstance(metadata, dict):
        metadata_conversation_id = metadata.get("conversation_id")
        metadata_session_id = metadata.get("session_id")
        metadata_thread_id = metadata.get("thread_id")

    return _first_nonempty_string(
        metadata_conversation_id,
        metadata_session_id,
        metadata_thread_id,
        getattr(run_context, "conversation_id", None),
        getattr(run_context, "session_id", None),
        getattr(run_context, "thread_id", None),
    )


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


def _apply_tenant_assistant_config(agent: Agent | None = None, team: Team | None = None, **kwargs: Any) -> None:
    """
    Agno Pre-Hook: Injects the tenant's specific LLM model and API key.
    """
    target = agent or team
    if not target:
        return
        
    run_context = getattr(target, "run_context", None)
    if not run_context:
        return

    metadata = getattr(run_context, "metadata", None)
    if not isinstance(metadata, dict):
        return

    client_id = _get_run_client_id(run_context)
    if not client_id:
        # In a test environment, you might want to mock this or safely return instead of throwing
        raise RuntimeError("Tenant client ID is required for jurisdiction-scoped assistant runs.")

    provider_keys, model_targets, agent_prompts = _load_tenant_assistant_config(client_id)
    
    # Build a map of all agents in the team (or just the solo agent)
    targets_by_id = {str(getattr(agent, "id", "") or ""): agent}
    if isinstance(agent, Team):
        for member in getattr(agent, "members", []):
            member_id = str(getattr(member, "id", "") or "")
            if member_id:
                targets_by_id[member_id] = member

    original_models: dict[str, Any] = {}
    original_instructions: dict[str, Any] = {}
    applied_targets: dict[str, dict[str, str | None]] = {}

    # Iterate over the target definitions to update models dynamically
    for target_id in ASSISTANT_TARGET_IDS:
        config = _resolve_target_config(target_id, model_targets)
        provider = "gemini"
        model_id = str(config.get("model_id") or "").strip()
        base_url = str(config.get("base_url") or "").strip() or None
        api_key = provider_keys.get("gemini")
        resolved_target = targets_by_id.get(target_id)

        if not resolved_target or not model_id or not api_key:
            continue

        # Gemini is the only supported assistant provider now.
            
        original_models[target_id] = getattr(resolved_target, "model", None)
        
        # Inject the tenant-specific model
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


def _record_run_telemetry(agent: Agent | None = None, team: Team | None = None, run_response: Any = None, **kwargs: Any) -> None:
    """
    Agno Post-Hook: Records execution telemetry including LLM token usage and latency.
    """
    target = agent or team
    if not target:
        return

    run_context = getattr(target, "run_context", None)
    if not run_context:
        return

    client_id = _get_run_client_id(run_context)
    metadata = getattr(run_context, "metadata", {}) or {}

    # Agno inherently passes metrics via the RunResponse object
    metrics = getattr(run_response, "metrics", {})

    payload = {
        "run_scope": "team" if isinstance(agent, Team) else "agent",
        "agent_id": str(getattr(agent, "id", "") or "") or None,
        "conversation_id": _get_run_conversation_id(run_context),
        "message_id": metadata.get("message_id"),
        "run_id": metadata.get("run_id"),
        "session_id": metadata.get("session_id") or getattr(agent, "session_id", None),
        "model_trace": get_model_trace(getattr(agent, "model", None)),
        "metrics": metrics, # Telemetry successfully captured!
    }

    record_assistant_run_telemetry(client_id=client_id, payload=payload)
