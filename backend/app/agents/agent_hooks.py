import logging
from typing import Any

from app.agents.factory import build_agent_model
from app.agents.assistant_defaults import (
    CODE_DEFAULT_ASSISTANT_MODEL_TARGETS,
    CUSTOMER_ZONING_ASSISTANT_TARGET_ID,
)
from app.agents.hooks import _load_tenant_assistant_config

# Import the base utils we just created
from app.agents.agent_utils import _get_run_context, _get_client_id

logger = logging.getLogger(__name__)

ASSISTANT_TARGET_IDS = [
    CUSTOMER_ZONING_ASSISTANT_TARGET_ID,
    "customer_zoning_team",
    "code-researcher-agent",
    "property-specialist-agent",
]

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

    provider_keys, _agent_prompts = _load_tenant_assistant_config(client_id)
    logger.debug(
        "Applying tenant assistant config client_id=%s target=%s provider_keys=%s",
        client_id,
        getattr(target, "id", None),
        sorted(provider_keys.keys()) if isinstance(provider_keys, dict) else None,
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
            continue

        provider = "gemini"
        default_model_id = str(
            CODE_DEFAULT_ASSISTANT_MODEL_TARGETS.get(target_name, {}).get("model_id") or ""
        ).strip()
        model_id = default_model_id
        base_url = None
        api_key = provider_keys.get("gemini") if isinstance(provider_keys, dict) else None
        if not model_id or not api_key:
            logger.warning(
                "Assistant model config incomplete client_id=%s target=%s model_id=%s gemini_key_present=%s",
                client_id,
                target_name,
                bool(model_id),
                bool(api_key),
            )
            continue

        resolved_target.model = build_agent_model(
            provider=provider,
            model_id=model_id,
            api_key=api_key,
            base_url=base_url,
            allow_env_fallback=False,
        )
