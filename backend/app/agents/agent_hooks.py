import logging
from typing import Any

from app.agents.factory import build_agent_model, get_model_trace
from app.agents.assistant_defaults import (
    CODE_DEFAULT_ASSISTANT_MODEL_TARGETS,
    CUSTOMER_ZONING_ASSISTANT_TARGET_ID,
)
from app.agents.hooks import _load_tenant_assistant_config as _hooks_load_tenant_assistant_config
from app.services.assistant_telemetry_service import record_assistant_run_telemetry
from app.services.assistant_observability import append_run_trace

# Import the base utils we just created
from app.agents.agent_utils import _first_nonempty_string, _get_run_context, _get_client_id, _get_conversation_id

_MODEL_OVERRIDE_METADATA_KEY = "assistant_model_id"
_MODEL_OVERRIDE_STATE_KEY = "_assistant_model_override_active"
_TENANT_ASSISTANT_CONFIG_STATE_KEY = "_tenant_assistant_config_active"

logger = logging.getLogger(__name__)

ASSISTANT_TARGET_IDS = [
    CUSTOMER_ZONING_ASSISTANT_TARGET_ID,
    "customer_zoning_team",
    "code-researcher-agent",
    "property-specialist-agent",
]

def _apply_model_override(agent: Any = None, run_context: Any = None, **kwargs: Any) -> None:
    target = agent
    if target is None:
        return

    active_context = run_context or _get_run_context(target, **kwargs)
    if active_context is None:
        return

    metadata = getattr(active_context, "metadata", None)
    if not isinstance(metadata, dict):
        return

    model_id = _first_nonempty_string(metadata.get(_MODEL_OVERRIDE_METADATA_KEY))
    if not model_id:
        return

    state = metadata.get(_MODEL_OVERRIDE_STATE_KEY)
    if not isinstance(state, dict):
        state = {}
        metadata[_MODEL_OVERRIDE_STATE_KEY] = state

    if "original_model" not in state:
        state["original_model"] = getattr(target, "model", None)

    target.model = build_agent_model(provider="gemini", model_id_override=model_id)

def _restore_model_override(agent: Any = None, run_context: Any = None, **kwargs: Any) -> None:
    target = agent
    if target is None:
        return

    active_context = run_context or _get_run_context(target, **kwargs)
    if active_context is None:
        return

    metadata = getattr(active_context, "metadata", None)
    if not isinstance(metadata, dict):
        return

    state = metadata.get(_MODEL_OVERRIDE_STATE_KEY)
    if not isinstance(state, dict):
        return

    original_model = state.get("original_model")
    if original_model is not None:
        target.model = original_model

    metadata.pop(_MODEL_OVERRIDE_STATE_KEY, None)

def _load_tenant_assistant_config(client_id: str):
    return _hooks_load_tenant_assistant_config(client_id)

def _resolve_gemini_target_config(target_id: str, model_targets: dict[str, dict[str, str | None]]) -> dict[str, str | None]:
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

def _apply_tenant_assistant_config(agent: Any = None, team: Any = None, **kwargs: Any) -> None:
    target = agent or team
    if target is None:
        return

    run_context = _get_run_context(target, **kwargs)
    if run_context is None:
        return

    client_id = _get_client_id(run_context, dependencies=kwargs.get("dependencies"))
    if not client_id:
        return

    append_run_trace(
        run_context,
        {
            "event": "assistant.team.config.start",
            "client_id": client_id,
            "target_id": getattr(target, "id", None),
            "member_ids": [str(getattr(member, "id", "") or "").strip() for member in getattr(target, "members", []) or []],
        },
    )

    provider_keys, model_targets, _agent_prompts = _load_tenant_assistant_config(client_id)
    logger.debug(
        "Applying tenant assistant config client_id=%s target=%s provider_keys=%s model_targets=%s",
        client_id,
        getattr(target, "id", None),
        sorted(provider_keys.keys()) if isinstance(provider_keys, dict) else None,
        sorted(model_targets.keys()) if isinstance(model_targets, dict) else None,
    )
    targets_by_id: dict[str, Any] = {}

    target_id = str(getattr(target, "id", "") or "").strip()
    if target_id:
        targets_by_id[target_id] = target

    for member in getattr(target, "members", []) or []:
        member_id = str(getattr(member, "id", "") or "").strip()
        if member_id:
            targets_by_id[member_id] = member

    for target_name in ASSISTANT_TARGET_IDS:
        resolved_target = targets_by_id.get(target_name)
        if resolved_target is None:
            append_run_trace(
                run_context,
                {
                    "event": "assistant.target.model.skipped",
                    "target_id": target_name,
                    "reason": "target_not_present_in_team",
                },
            )
            continue

        config = _resolve_gemini_target_config(target_name, model_targets if isinstance(model_targets, dict) else {})
        provider = "gemini"
        model_id = str(config.get("model_id") or "").strip()
        base_url = str(config.get("base_url") or "").strip() or None
        api_key = provider_keys.get("gemini") if isinstance(provider_keys, dict) else None
        if not model_id or not api_key:
            logger.warning(
                "Assistant model config incomplete client_id=%s target=%s model_id=%s gemini_key_present=%s",
                client_id,
                target_name,
                bool(model_id),
                bool(api_key),
            )
            append_run_trace(
                run_context,
                {
                    "event": "assistant.target.model.skipped",
                    "target_id": target_name,
                    "reason": "missing_model_id_or_api_key",
                    "has_model_id": bool(model_id),
                    "has_gemini_key": bool(api_key),
                },
            )
            continue

        resolved_target.model = build_agent_model(
            provider=provider,
            model_id=model_id,
            api_key=api_key,
            base_url=base_url,
            allow_env_fallback=False,
        )
        append_run_trace(
            run_context,
            {
                "event": "assistant.target.model.applied",
                "target_id": target_name,
                "provider": provider,
                "model_id": model_id,
                "base_url": base_url,
                "model_trace": get_model_trace(resolved_target.model),
            },
        )

    append_run_trace(
        run_context,
        {
            "event": "assistant.team.config.complete",
            "client_id": client_id,
            "applied_targets": [target_name for target_name in ASSISTANT_TARGET_IDS if target_name in targets_by_id],
            "target_count": len([target_name for target_name in ASSISTANT_TARGET_IDS if target_name in targets_by_id]),
        },
    )

def _record_run_telemetry(agent: Any = None, team: Any = None, run_output: Any = None, **kwargs: Any) -> None:
    target = agent or team
    if target is None:
        return

    run_context = _get_run_context(target, **kwargs)
    if run_context is None:
        return

    metadata = kwargs.get("metadata")
    if not isinstance(metadata, dict):
        metadata = getattr(run_context, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}

    run_output_value = run_output if run_output is not None else kwargs.get("run_response")
    metrics = None
    if isinstance(run_output_value, dict):
        metrics = run_output_value.get("usage") or run_output_value.get("metrics")
    else:
        metrics = getattr(run_output_value, "metrics", None)

    payload = {
        "conversation_id": _get_conversation_id(run_context, run_output_value),
        "session_id": _first_nonempty_string(
            metadata.get("session_id"),
            getattr(run_context, "session_id", None),
            getattr(run_output_value, "session_id", None),
        ),
        "message_id": _first_nonempty_string(
            metadata.get("message_id"),
            getattr(run_context, "message_id", None),
            getattr(run_output_value, "message_id", None),
            kwargs.get("message_id"),
        ),
        "run_id": _first_nonempty_string(
            metadata.get("run_id"),
            getattr(run_context, "run_id", None),
            getattr(run_output_value, "run_id", None),
            kwargs.get("run_id"),
        ),
        "metrics": metrics,
        "run_output": run_output_value,
    }

    append_run_trace(
        run_context,
        {
            "event": "assistant.run.telemetry.recorded",
            "agent_id": payload.get("agent_id"),
            "run_scope": payload.get("run_scope"),
            "conversation_id": payload.get("conversation_id"),
            "session_id": payload.get("session_id"),
            "message_id": payload.get("message_id"),
            "run_id": payload.get("run_id"),
            "model_trace": payload.get("model_trace"),
            "metrics_present": bool(metrics),
        },
    )

    record_assistant_run_telemetry(
        client_id=_get_client_id(run_context, dependencies=kwargs.get("dependencies")),
        payload=payload,
    )
