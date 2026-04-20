from __future__ import annotations

from sqlalchemy import select

from agno.run import RunContext

from app.db.models import TenantClient
from app.db.session import SessionLocal
from app.services.embed_service import decode_embed_session_token
from app.services.platform_settings_service import get_platform_assistant_settings_json
from app.services.tenant_service import (
    get_tenant_assistant_agent_prompts,
    get_tenant_assistant_settings,
    merge_assistant_agent_prompts,
    merge_assistant_provider_keys,
)


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


def _load_tenant_assistant_config(
    client_id: str,
) -> tuple[dict[str, str | None], dict[str, str]]:
    with SessionLocal() as db:
        platform_settings_json = get_platform_assistant_settings_json(db)
        platform_provider_keys, _ = get_tenant_assistant_settings(platform_settings_json)
        platform_agent_prompts = get_tenant_assistant_agent_prompts(platform_settings_json)
        tenant_client = db.scalar(select(TenantClient).where(TenantClient.client_id == client_id))

        if tenant_client is None:
            return platform_provider_keys, platform_agent_prompts

        provider_keys, _ = get_tenant_assistant_settings(tenant_client.settings_json)
        agent_prompts = get_tenant_assistant_agent_prompts(tenant_client.settings_json)

        return (
            merge_assistant_provider_keys(platform_provider_keys, provider_keys),
            merge_assistant_agent_prompts(platform_agent_prompts, agent_prompts),
        )
