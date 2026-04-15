"""Persistence helpers for agent run telemetry."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from sqlalchemy import func, inspect, select

from app.db.models import AssistantRunTelemetry, TenantClient
from app.db.session import SessionLocal


logger = logging.getLogger(__name__)
_TELEMETRY_DEBUG_COUNTERS = {
    "received": 0,
    "persisted": 0,
    "missing_metrics": 0,
}


def _resolve_tenant_id(db, client_id: str | None) -> str | None:
    normalized = (client_id or "").strip()
    if not normalized:
        return None
    tenant = db.scalar(select(TenantClient).where(TenantClient.client_id == normalized))
    return tenant.id if tenant else None


def _has_assistant_run_telemetry_storage(db) -> bool:
    bind = db.get_bind()
    return bool(bind is not None and inspect(bind).has_table("assistant_run_telemetry"))


def _empty_telemetry_payload() -> dict[str, Any]:
    return {
        "summary": {
            "total_runs": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
        },
        "runs": [],
        "pagination": {
            "page": 1,
            "page_size": 50,
            "total_runs": 0,
            "total_pages": 0,
            "has_previous": False,
            "has_next": False,
            "search": None,
        },
    }


def _coerce_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float, Decimal)):
        try:
            return int(value)
        except Exception:
            return 0
    if isinstance(value, str) and value.strip():
        try:
            return int(float(value))
        except Exception:
            return 0
    return 0


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return float(value)
        except Exception:
            return None
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except Exception:
            return None
    return None


def _to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    to_dict = getattr(value, "model_dump", None)
    if callable(to_dict):
        try:
            result = to_dict()
            if isinstance(result, dict):
                return result
        except Exception:
            pass
    to_dict = getattr(value, "dict", None)
    if callable(to_dict):
        try:
            result = to_dict()
            if isinstance(result, dict):
                return result
        except Exception:
            pass
    try:
        result = vars(value)
        if isinstance(result, dict) and result:
            return result
    except Exception:
        pass
    return {}


def _first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
    return None


def _extract_candidate_metrics_sources(payload: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    candidates = [
        payload.get("metrics"),
        payload.get("run_output"),
        payload.get("response"),
        payload.get("result"),
    ]
    for candidate in candidates:
        candidate_dict = _to_dict(candidate)
        if candidate_dict:
            for nested_key in ("metrics", "usage", "usage_metrics", "token_usage", "statistics"):
                nested_dict = _to_dict(candidate_dict.get(nested_key))
                if nested_dict:
                    sources.append(nested_dict)
            sources.append(candidate_dict)
    return sources


def _read_metric(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = source.get(key)
        if value is not None:
            return value
    return None


def _extract_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    metrics_dict: dict[str, Any] = {}
    for source in _extract_candidate_metrics_sources(payload):
        metrics_dict = source
        if any(
            key in source
            for key in (
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "cost",
                "time_to_first_token",
                "duration",
                "duration_seconds",
                "details",
                "prompt_tokens",
                "completion_tokens",
                "usage",
                "usage_metrics",
                "token_usage",
            )
        ):
            break

    details = metrics_dict.get("details") if isinstance(metrics_dict.get("details"), dict) else {}

    primary_model = None
    for key in ("model", "output_model", "parser_model", "memory_model", "reasoning_model"):
        detail_items = details.get(key)
        if isinstance(detail_items, list) and detail_items:
            candidate = _to_dict(detail_items[0])
            if candidate:
                primary_model = candidate
                break

    input_tokens = _coerce_int(
        _read_metric(metrics_dict, "input_tokens", "prompt_tokens", "prompt_token_count", "inputTokenCount")
    )
    output_tokens = _coerce_int(
        _read_metric(metrics_dict, "output_tokens", "completion_tokens", "completion_token_count", "outputTokenCount")
    )
    total_tokens = _coerce_int(_read_metric(metrics_dict, "total_tokens", "total_token_count", "token_count"))
    if total_tokens == 0 and (input_tokens or output_tokens):
        total_tokens = input_tokens + output_tokens

    duration_value = _read_metric(metrics_dict, "duration", "duration_seconds", "elapsed_seconds")
    if duration_value is None and isinstance(metrics_dict.get("timing"), dict):
        duration_value = _read_metric(metrics_dict["timing"], "duration", "duration_seconds", "elapsed_seconds")

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost": _coerce_float(_read_metric(metrics_dict, "cost", "estimated_cost", "total_cost")),
        "time_to_first_token": _coerce_float(
            _read_metric(metrics_dict, "time_to_first_token", "ttft", "timeToFirstToken")
        ),
        "duration_seconds": _coerce_float(duration_value),
        "metrics_json": metrics_dict or None,
        "primary_model": primary_model,
    }


def record_assistant_run_telemetry(*, client_id: str | None, payload: dict[str, Any]) -> None:
    """Best-effort persistence of agent telemetry events."""
    try:
        with SessionLocal() as db:
            if not _has_assistant_run_telemetry_storage(db):
                return
            tenant_client_id = _resolve_tenant_id(db, client_id)
            if tenant_client_id is None:
                return

            _TELEMETRY_DEBUG_COUNTERS["received"] += 1
            metrics = _extract_metrics(payload)
            if not (metrics["input_tokens"] or metrics["output_tokens"] or metrics["total_tokens"]):
                _TELEMETRY_DEBUG_COUNTERS["missing_metrics"] += 1
            model_trace = payload.get("model_trace")
            if not isinstance(model_trace, dict):
                model_trace = {}
            metrics_json = dict(metrics["metrics_json"] or {})
            if model_trace:
                metrics_json["model_trace"] = model_trace

            primary_model = metrics["primary_model"] or {}
            run_scope = str(payload.get("run_scope") or "team").strip() or "team"

            event = AssistantRunTelemetry(
                tenant_client_id=tenant_client_id,
                run_scope=run_scope,
                agent_id=str(payload.get("agent_id") or "") or None,
                conversation_id=str(payload.get("conversation_id") or "") or None,
                message_id=str(payload.get("message_id") or "") or None,
                run_id=str(payload.get("run_id") or "") or None,
                session_id=str(payload.get("session_id") or "") or None,
                model_provider=str(
                    model_trace.get("provider")
                    or primary_model.get("provider")
                    or ""
                )
                or None,
                model_name=str(
                    model_trace.get("model_name")
                    or primary_model.get("model_name")
                    or ""
                )
                or None,
                model_id=str(
                    model_trace.get("model_id")
                    or primary_model.get("id")
                    or ""
                )
                or None,
                input_tokens=metrics["input_tokens"],
                output_tokens=metrics["output_tokens"],
                total_tokens=metrics["total_tokens"],
                cost=metrics["cost"],
                time_to_first_token=metrics["time_to_first_token"],
                duration_seconds=metrics["duration_seconds"],
                metrics_json=metrics_json or None,
            )
            db.add(event)
            db.commit()
            _TELEMETRY_DEBUG_COUNTERS["persisted"] += 1
            logger.info(
                "assistant telemetry recorded: received=%s persisted=%s missing_metrics=%s client_id=%s run_id=%s model_id=%s input_tokens=%s output_tokens=%s total_tokens=%s",
                _TELEMETRY_DEBUG_COUNTERS["received"],
                _TELEMETRY_DEBUG_COUNTERS["persisted"],
                _TELEMETRY_DEBUG_COUNTERS["missing_metrics"],
                client_id,
                payload.get("run_id"),
                event.model_id,
                event.input_tokens,
                event.output_tokens,
                event.total_tokens,
            )
    except Exception:
        return


def list_assistant_run_telemetry(
    *,
    client_id: str | None,
    limit: int = 50,
    page: int = 1,
    search: str | None = None,
) -> dict[str, Any]:
    with SessionLocal() as db:
        if not _has_assistant_run_telemetry_storage(db):
            return _empty_telemetry_payload()
        tenant = db.scalar(select(TenantClient).where(TenantClient.client_id == (client_id or "").strip()))
        if tenant is None:
            return _empty_telemetry_payload()

        page = max(1, int(page or 1))
        page_size = max(1, min(limit, 200))
        search_term = (search or "").strip().lower()

        base_stmt = select(AssistantRunTelemetry).where(AssistantRunTelemetry.tenant_client_id == tenant.id)
        if search_term:
            pattern = f"%{search_term}%"
            base_stmt = base_stmt.where(
                func.lower(func.coalesce(AssistantRunTelemetry.conversation_id, "")).like(pattern)
                | func.lower(func.coalesce(AssistantRunTelemetry.session_id, "")).like(pattern)
                | func.lower(func.coalesce(AssistantRunTelemetry.run_id, "")).like(pattern)
                | func.lower(func.coalesce(AssistantRunTelemetry.agent_id, "")).like(pattern)
                | func.lower(func.coalesce(AssistantRunTelemetry.model_id, "")).like(pattern)
                | func.lower(func.coalesce(AssistantRunTelemetry.model_name, "")).like(pattern)
                | func.lower(func.coalesce(AssistantRunTelemetry.model_provider, "")).like(pattern)
            )

        total_runs = db.scalar(select(func.count(AssistantRunTelemetry.id)).select_from(base_stmt.subquery())) or 0
        total_pages = max(1, (int(total_runs) + page_size - 1) // page_size) if total_runs else 0
        page = min(page, total_pages or 1)
        offset = (page - 1) * page_size

        runs_stmt = (
            base_stmt
            .order_by(AssistantRunTelemetry.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = db.scalars(runs_stmt).all()

        summary_subquery = base_stmt.subquery()
        summary_stmt = select(
            func.count(summary_subquery.c.id),
            func.coalesce(func.sum(summary_subquery.c.input_tokens), 0),
            func.coalesce(func.sum(summary_subquery.c.output_tokens), 0),
            func.coalesce(func.sum(summary_subquery.c.total_tokens), 0),
            func.coalesce(func.sum(summary_subquery.c.cost), 0),
        ).select_from(summary_subquery)

        total_runs, total_input_tokens, total_output_tokens, total_total_tokens, total_cost = db.execute(
            summary_stmt
        ).one()

        return {
            "summary": {
                "total_runs": int(total_runs or 0),
                "input_tokens": int(total_input_tokens or 0),
                "output_tokens": int(total_output_tokens or 0),
                "total_tokens": int(total_total_tokens or 0),
                "cost": float(total_cost or 0),
            },
            "runs": [
                {
                    "id": row.id,
                    "run_scope": row.run_scope,
                    "agent_id": row.agent_id,
                    "conversation_id": row.conversation_id,
                    "message_id": row.message_id,
                    "run_id": row.run_id,
                    "session_id": row.session_id,
                    "model_provider": row.model_provider,
                    "model_name": row.model_name,
                    "model_id": row.model_id,
                    "input_tokens": row.input_tokens,
                    "output_tokens": row.output_tokens,
                    "total_tokens": row.total_tokens,
                    "cost": float(row.cost) if row.cost is not None else None,
                    "time_to_first_token": float(row.time_to_first_token) if row.time_to_first_token is not None else None,
                    "duration_seconds": float(row.duration_seconds) if row.duration_seconds is not None else None,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "metrics_json": row.metrics_json,
                }
                for row in rows
            ],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_runs": int(total_runs or 0),
                "total_pages": total_pages,
                "has_previous": page > 1,
                "has_next": bool(total_pages and page < total_pages),
                "search": search_term or None,
            },
        }
