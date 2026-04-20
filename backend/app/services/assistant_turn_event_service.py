"""Persistence helpers for assistant turn-level observability events."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.models import AssistantTurnEvent, TenantClient
from app.db.session import SessionLocal


def _resolve_tenant_id(db, client_id: str | None) -> str | None:
    normalized = (client_id or "").strip()
    if not normalized:
        return None
    tenant = db.scalar(select(TenantClient).where(TenantClient.client_id == normalized))
    return tenant.id if tenant else None


def record_assistant_turn_event(*, client_id: str | None, payload: dict[str, Any]) -> None:
    """Best-effort persistence of assistant turn events.

    The call intentionally does not raise so assistant responses are never blocked by
    observability/logging storage failures.
    """
    try:
        with SessionLocal() as db:
            tenant_client_id = _resolve_tenant_id(db, client_id)
            assistant_turn = payload.get("assistant_turn") if isinstance(payload, dict) else {}
            policy_decision = payload.get("policy_decision") if isinstance(payload, dict) else {}
            event = AssistantTurnEvent(
                tenant_client_id=tenant_client_id,
                conversation_id=str(payload.get("conversation_id") or "") or None,
                message_id=str(payload.get("message_id") or "") or None,
                run_id=str(payload.get("run_id") or "") or None,
                agent_id=str(payload.get("agent_id") or "") or None,
                intent_type=str((assistant_turn or {}).get("intent_type") or "") or None,
                jurisdiction_status=str((assistant_turn or {}).get("jurisdiction_status") or "") or None,
                policy_decision=str((policy_decision or {}).get("decision") or "") or None,
                reason_code=str((policy_decision or {}).get("reason_code") or "") or None,
                payload_json=payload,
            )
            db.add(event)
            db.commit()
    except Exception:
        return
