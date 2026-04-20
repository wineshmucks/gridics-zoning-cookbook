"""Shared Agno session storage helpers."""

from __future__ import annotations

import logging
import uuid
from functools import lru_cache
from dataclasses import dataclass
from typing import Any

from agno.db.postgres import PostgresDb
from agno.db.postgres.async_postgres import AsyncPostgresDb
from agno.db.base import SessionType
from agno.session import AgentSession, TeamSession, WorkflowSession
from sqlalchemy import MetaData, Table, func, select
from app.core.config import settings
from app.db.session import engine as sync_engine

logger = logging.getLogger(__name__)

_HISTORY_RUN_CAP = 5
_DEFAULT_DB_SCHEMA = "agent_os"
_DEFAULT_METRICS_TABLE = "aos_metrics"
_DEFAULT_TRACES_TABLE = "aos_traces"
_DEFAULT_SPANS_TABLE = "aos_spans"
_DEFAULT_CONVERSATION_COMPONENT_ID = "customer_zoning_team"
_DEFAULT_CONVERSATION_COMPONENT_IDS = (
    "customer_zoning_team",
    "customer-zoning-team",
    "customer-zoning-agent",
)


@dataclass(frozen=True)
class AgnoStorageConfig:
    enabled: bool
    session_table: str
    store_history_messages: bool
    num_history_runs: int
    db_schema: str = _DEFAULT_DB_SCHEMA
    metrics_table: str = _DEFAULT_METRICS_TABLE
    traces_table: str = _DEFAULT_TRACES_TABLE
    spans_table: str = _DEFAULT_SPANS_TABLE


def _normalize_table_name(candidate: str | None, fallback: str) -> str:
    value = str(candidate or "").strip()
    return value or fallback


def _cap_history_runs(value: int | str | None) -> int:
    try:
        resolved = int(value) if value is not None else _HISTORY_RUN_CAP
    except (TypeError, ValueError):
        resolved = _HISTORY_RUN_CAP
    return max(1, min(resolved, _HISTORY_RUN_CAP))


def get_agno_storage_config() -> AgnoStorageConfig:
    enabled = bool(settings.agno_sessions_enabled)
    store_history_messages = bool(settings.agno_store_history_messages) if enabled else False
    num_history_runs = _cap_history_runs(settings.agno_num_history_runs) if enabled else _HISTORY_RUN_CAP

    if enabled and store_history_messages:
        logger.warning(
            "Agno session storage is configured to persist full history messages. "
            "This can significantly increase PostgreSQL storage usage because Agno stores expanded history per run."
        )

    return AgnoStorageConfig(
        enabled=enabled,
        session_table=_normalize_table_name(settings.agno_session_table, "aos_sessions"),
        store_history_messages=store_history_messages,
        num_history_runs=num_history_runs,
    )


def get_agno_db(config: AgnoStorageConfig | None = None) -> PostgresDb | None:
    config = config or get_agno_storage_config()
    if not config.enabled:
        logger.info(
            "Agno session persistence disabled; runs will not be stored in PostgreSQL. session_table=%s",
            config.session_table,
        )
        return None

    try:
        return PostgresDb(
            db_url=settings.database_url,
            db_engine=sync_engine,
            db_schema=config.db_schema,
            session_table=config.session_table,
            metrics_table=config.metrics_table,
            traces_table=config.traces_table,
            spans_table=config.spans_table,
        )
    except Exception:
        logger.exception(
            "Failed to initialize Agno PostgreSQL session storage; continuing without persistent sessions. "
            "session_table=%s",
            config.session_table,
        )
        return None


def get_async_agno_db(config: AgnoStorageConfig | None = None) -> AsyncPostgresDb | None:
    config = config or get_agno_storage_config()
    if not config.enabled:
        return None

    try:
        return AsyncPostgresDb(
            db_url=settings.database_url,
            db_schema=config.db_schema,
            session_table=config.session_table,
            metrics_table=config.metrics_table,
            traces_table=config.traces_table,
            spans_table=config.spans_table,
        )
    except Exception:
        logger.exception(
            "Failed to initialize async Agno PostgreSQL session storage; continuing without persistent sessions. "
            "session_table=%s",
            config.session_table,
        )
        return None


def build_agno_session_kwargs(*, enable_history: bool = True) -> dict[str, Any]:
    config = get_agno_storage_config()
    db = get_agno_db(config) if config.enabled else None
    history_enabled = bool(config.enabled and enable_history and db is not None)
    return {
        "db": db,
        "add_history_to_context": history_enabled,
        "num_history_runs": config.num_history_runs if history_enabled else None,
        "store_history_messages": bool(config.store_history_messages and history_enabled),
    }


def _first_nonempty_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            resolved = value.strip()
            if resolved:
                return resolved
    return None


def resolve_agno_session_id(*, run_context: Any = None, run_output: Any = None, **kwargs: Any) -> str:
    metadata = kwargs.get("metadata")
    if not isinstance(metadata, dict):
        metadata = getattr(run_context, "metadata", None)

    metadata_conversation_id = None
    metadata_session_id = None
    metadata_thread_id = None
    metadata_chat_id = None
    if isinstance(metadata, dict):
        metadata_conversation_id = metadata.get("conversation_id")
        metadata_session_id = metadata.get("session_id")
        metadata_thread_id = metadata.get("thread_id")
        metadata_chat_id = metadata.get("chat_id")

    return _first_nonempty_string(
        metadata_conversation_id,
        metadata_session_id,
        metadata_thread_id,
        metadata_chat_id,
        getattr(run_context, "conversation_id", None),
        getattr(run_context, "session_id", None),
        getattr(run_context, "thread_id", None),
        getattr(run_context, "chat_id", None),
        getattr(run_output, "conversation_id", None),
        getattr(run_output, "session_id", None),
        getattr(run_output, "thread_id", None),
        getattr(run_output, "chat_id", None),
    ) or uuid.uuid4().hex


def _metric_value(source: Any, *names: str, default: Any = 0) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        for name in names:
            value = source.get(name)
            if value is not None:
                return value
        return default
    for name in names:
        value = getattr(source, name, None)
        if value is not None:
            return value
    return default


def _normalize_session_type(session_type: str | SessionType | None) -> str:
    if isinstance(session_type, SessionType):
        return session_type.value
    return str(session_type or SessionType.TEAM.value).strip() or SessionType.TEAM.value


@lru_cache(maxsize=8)
def _get_session_table(schema: str, session_table: str) -> Table:
    metadata = MetaData(schema=schema or None)
    return Table(session_table, metadata, autoload_with=sync_engine)


def _resolve_session_table(config: AgnoStorageConfig | None = None) -> Table | None:
    config = config or get_agno_storage_config()
    if not config.enabled:
        return None
    try:
        return _get_session_table(config.db_schema, config.session_table)
    except Exception:
        logger.exception(
            "Failed to reflect Agno session table; continuing without indexed conversation listing. session_table=%s",
            config.session_table,
        )
        return None


def _tenant_client_filter(table: Table, client_id: str):
    metadata_column = table.c["metadata"]
    client_key = func.coalesce(
        metadata_column.op("->>")("tenant_client_id"),
        metadata_column.op("->>")("client_id"),
    )
    return client_key == client_id


def _session_component_filter(table: Table, session_type: str, component_ids: tuple[str, ...] | None):
    if not component_ids:
        return None
    valid_ids = tuple(str(component_id).strip() for component_id in component_ids if str(component_id).strip())
    if not valid_ids:
        return None
    if session_type == SessionType.AGENT.value:
        return table.c.agent_id.in_(valid_ids)
    if session_type == SessionType.WORKFLOW.value:
        return table.c.workflow_id.in_(valid_ids)
    return table.c.team_id.in_(valid_ids)


def _session_row_to_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    return dict(row or {})


def _row_to_session_object(row: dict[str, Any], session_type: str):
    normalized_session_type = _normalize_session_type(session_type)
    if normalized_session_type == SessionType.AGENT.value:
        return AgentSession.from_dict(row)
    if normalized_session_type == SessionType.WORKFLOW.value:
        return WorkflowSession.from_dict(row)
    return TeamSession.from_dict({**row, "session_type": SessionType.TEAM.value})


def _attr_or_item(source: Any, *names: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        for name in names:
            if name in source and source[name] is not None:
                return source[name]
        return default
    for name in names:
        value = getattr(source, name, None)
        if value is not None:
            return value
    return default


def _normalize_model_metrics_item(model_metrics: Any, *, kind: str | None = None) -> dict[str, Any]:
    provider = _metric_value(model_metrics, "provider", default=None)
    model_id = _metric_value(model_metrics, "id", "model_id", default=None)
    normalized = {
        "kind": kind,
        "provider": provider,
        "model_id": model_id,
        "input_tokens": int(_metric_value(model_metrics, "input_tokens", default=0) or 0),
        "output_tokens": int(_metric_value(model_metrics, "output_tokens", default=0) or 0),
        "total_tokens": int(_metric_value(model_metrics, "total_tokens", default=0) or 0),
        "reasoning_tokens": int(_metric_value(model_metrics, "reasoning_tokens", default=0) or 0),
        "cache_read_tokens": int(_metric_value(model_metrics, "cache_read_tokens", "cached_tokens", default=0) or 0),
        "cache_write_tokens": int(_metric_value(model_metrics, "cache_write_tokens", default=0) or 0),
        "cost": _metric_value(model_metrics, "cost", default=None),
    }
    return normalized


def _collect_model_usage(details: Any) -> list[dict[str, Any]]:
    model_usage: list[dict[str, Any]] = []
    if not isinstance(details, dict):
        return model_usage

    for kind, entries in details.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            model_usage.append(_normalize_model_metrics_item(entry, kind=str(kind)))
    return model_usage


def extract_run_usage_metrics(
    run_output: Any = None,
    *,
    agent: Any = None,
    team: Any = None,
    session: Any = None,
    metadata: dict[str, Any] | None = None,
    run_context: Any = None,
) -> dict[str, Any]:
    metrics = _attr_or_item(run_output, "metrics")
    session_id = _first_nonempty_string(
        _attr_or_item(session, "session_id"),
        _attr_or_item(run_output, "session_id"),
        getattr(run_context, "session_id", None),
        (metadata or {}).get("conversation_id"),
        (metadata or {}).get("session_id"),
        (metadata or {}).get("thread_id"),
        (metadata or {}).get("chat_id"),
    )
    session_type = _first_nonempty_string(
        _attr_or_item(session, "session_type"),
        _attr_or_item(run_output, "session_type"),
    )
    agent_id = _first_nonempty_string(
        _attr_or_item(agent, "id"),
        _attr_or_item(team, "id"),
        _attr_or_item(run_output, "agent_id"),
    )
    team_id = _first_nonempty_string(_attr_or_item(team, "id"), _attr_or_item(run_output, "team_id"))
    model = _attr_or_item(run_output, "model") or _attr_or_item(agent, "model") or _attr_or_item(team, "model")
    model_provider = _first_nonempty_string(
        _attr_or_item(model, "_uzone_model_provider"),
        _attr_or_item(model, "provider"),
    )
    model_id = _first_nonempty_string(
        _attr_or_item(model, "_uzone_model_id"),
        _attr_or_item(model, "id", "model_id"),
        _attr_or_item(run_output, "model_id"),
    )

    details = _metric_value(metrics, "details", default=None)
    model_usage = _collect_model_usage(details)
    if not model_usage and (model_provider or model_id):
        model_usage = [
            {
                "kind": "model",
                "provider": model_provider,
                "model_id": model_id,
                "input_tokens": int(_metric_value(metrics, "input_tokens", default=0) or 0),
                "output_tokens": int(_metric_value(metrics, "output_tokens", default=0) or 0),
                "total_tokens": int(_metric_value(metrics, "total_tokens", default=0) or 0),
                "reasoning_tokens": int(_metric_value(metrics, "reasoning_tokens", default=0) or 0),
                "cache_read_tokens": int(_metric_value(metrics, "cache_read_tokens", "cached_tokens", default=0) or 0),
                "cache_write_tokens": int(_metric_value(metrics, "cache_write_tokens", default=0) or 0),
                "cost": _metric_value(metrics, "cost", default=None),
            }
        ]

    return {
        "session_id": session_id,
        "session_type": session_type,
        "run_id": _first_nonempty_string(_attr_or_item(run_output, "run_id"), getattr(run_context, "run_id", None)),
        "agent_id": agent_id,
        "team_id": team_id,
        "model_provider": model_provider,
        "model_id": model_id,
        "input_tokens": int(_metric_value(metrics, "input_tokens", default=0) or 0),
        "output_tokens": int(_metric_value(metrics, "output_tokens", default=0) or 0),
        "total_tokens": int(_metric_value(metrics, "total_tokens", default=0) or 0),
        "reasoning_tokens": int(_metric_value(metrics, "reasoning_tokens", default=0) or 0),
        "cache_read_tokens": int(_metric_value(metrics, "cache_read_tokens", "cached_tokens", default=0) or 0),
        "cache_write_tokens": int(_metric_value(metrics, "cache_write_tokens", default=0) or 0),
        "cost": _metric_value(metrics, "cost", default=None),
        "time_to_first_token": _metric_value(metrics, "time_to_first_token", default=None),
        "duration": _metric_value(metrics, "duration", "time", default=None),
        "model_usage": model_usage,
    }


def log_agno_run_metrics(
    agent: Any = None,
    team: Any = None,
    run_output: Any = None,
    session: Any = None,
    session_state: Any = None,
    dependencies: Any = None,
    metadata: dict[str, Any] | None = None,
    user_id: str | None = None,
    debug_mode: bool | None = None,
    run_context: Any = None,
) -> None:
    summary = extract_run_usage_metrics(
        run_output,
        agent=agent,
        team=team,
        session=session,
        metadata=metadata,
        run_context=run_context,
    )
    logger.info(
        "Agno run metrics session_id=%s run_id=%s agent_id=%s team_id=%s model=%s provider=%s input_tokens=%s output_tokens=%s total_tokens=%s cost=%s duration=%s",
        summary.get("session_id"),
        summary.get("run_id"),
        summary.get("agent_id"),
        summary.get("team_id"),
        summary.get("model_id"),
        summary.get("model_provider"),
        summary.get("input_tokens"),
        summary.get("output_tokens"),
        summary.get("total_tokens"),
        summary.get("cost"),
        summary.get("duration"),
    )


def _session_run_metrics(session: Any) -> list[dict[str, Any]]:
    runs = getattr(session, "runs", None)
    if isinstance(runs, list):
        return runs
    if isinstance(session, dict):
        raw_runs = session.get("runs")
        return raw_runs if isinstance(raw_runs, list) else []
    return []


def _aggregate_totals_for_runs(runs: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "reasoning_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "cost": 0.0,
        "duration": 0.0,
        "time_to_first_token_max": None,
    }
    model_usage_by_key: dict[tuple[str | None, str | None, str | None], dict[str, Any]] = {}

    for run in runs:
        run_summary = extract_run_usage_metrics(run)
        totals["input_tokens"] += int(run_summary["input_tokens"] or 0)
        totals["output_tokens"] += int(run_summary["output_tokens"] or 0)
        totals["total_tokens"] += int(run_summary["total_tokens"] or 0)
        totals["reasoning_tokens"] += int(run_summary["reasoning_tokens"] or 0)
        totals["cache_read_tokens"] += int(run_summary["cache_read_tokens"] or 0)
        totals["cache_write_tokens"] += int(run_summary["cache_write_tokens"] or 0)
        totals["cost"] += float(run_summary["cost"] or 0.0)
        totals["duration"] += float(run_summary["duration"] or 0.0)
        ttfb = run_summary["time_to_first_token"]
        if ttfb is not None:
            current_max = totals["time_to_first_token_max"]
            totals["time_to_first_token_max"] = ttfb if current_max is None else max(current_max, float(ttfb))

        for model_entry in run_summary["model_usage"]:
            key = (
                model_entry.get("kind"),
                model_entry.get("provider"),
                model_entry.get("model_id"),
            )
            existing = model_usage_by_key.setdefault(
                key,
                {
                    "kind": model_entry.get("kind"),
                    "provider": model_entry.get("provider"),
                    "model_id": model_entry.get("model_id"),
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "reasoning_tokens": 0,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                    "cost": 0.0,
                },
            )
            existing["input_tokens"] += int(model_entry.get("input_tokens") or 0)
            existing["output_tokens"] += int(model_entry.get("output_tokens") or 0)
            existing["total_tokens"] += int(model_entry.get("total_tokens") or 0)
            existing["reasoning_tokens"] += int(model_entry.get("reasoning_tokens") or 0)
            existing["cache_read_tokens"] += int(model_entry.get("cache_read_tokens") or 0)
            existing["cache_write_tokens"] += int(model_entry.get("cache_write_tokens") or 0)
            existing["cost"] += float(model_entry.get("cost") or 0.0)

    return totals, sorted(model_usage_by_key.values(), key=lambda item: (str(item["kind"]), str(item["provider"]), str(item["model_id"])))


def get_session_usage_totals(
    session_id: str,
    *,
    session_type: str | None = None,
    db: Any = None,
) -> dict[str, Any] | None:
    resolved_session_id = str(session_id or "").strip()
    if not resolved_session_id:
        return None

    session_type_candidates = [session_type] if session_type else ["team", "agent", "workflow"]
    session_db = db or get_agno_db()
    if session_db is None:
        return None

    for candidate in session_type_candidates:
        if not candidate:
            continue
        try:
            session = session_db.get_session(session_id=resolved_session_id, session_type=candidate)
        except Exception:
            logger.exception("Failed to load Agno session usage totals session_id=%s session_type=%s", resolved_session_id, candidate)
            continue
        if session is None:
            continue

        runs = _session_run_metrics(session)
        totals, model_usage = _aggregate_totals_for_runs(runs)
        return {
            "session_id": resolved_session_id,
            "session_type": _first_nonempty_string(getattr(session, "session_type", None), candidate),
            "run_count": len(runs),
            "totals": totals,
            "model_usage": model_usage,
        }

    return None


async def aget_session_usage_totals(
    session_id: str,
    *,
    session_type: str | None = None,
    db: AsyncPostgresDb | None = None,
) -> dict[str, Any] | None:
    resolved_session_id = str(session_id or "").strip()
    if not resolved_session_id:
        return None

    session_type_candidates = [session_type] if session_type else ["team", "agent", "workflow"]
    session_db = db or get_async_agno_db()
    if session_db is None:
        return None

    for candidate in session_type_candidates:
        if not candidate:
            continue
        try:
            session = await session_db.get_session(session_id=resolved_session_id, session_type=candidate)
        except Exception:
            logger.exception("Failed to load async Agno session usage totals session_id=%s session_type=%s", resolved_session_id, candidate)
            continue
        if session is None:
            continue

        runs = _session_run_metrics(session)
        totals, model_usage = _aggregate_totals_for_runs(runs)
        return {
            "session_id": resolved_session_id,
            "session_type": _first_nonempty_string(getattr(session, "session_type", None), candidate),
            "run_count": len(runs),
            "totals": totals,
            "model_usage": model_usage,
        }

    return None


def list_tenant_conversation_sessions(
    client_id: str,
    *,
    session_type: str | SessionType | tuple[str | SessionType, ...] | None = None,
    component_id: str | tuple[str, ...] | None = _DEFAULT_CONVERSATION_COMPONENT_IDS,
    limit: int = 25,
    offset: int = 0,
    config: AgnoStorageConfig | None = None,
) -> tuple[list[dict[str, Any]], int]:
    resolved_client_id = str(client_id or "").strip()
    if not resolved_client_id:
        return [], 0

    table = _resolve_session_table(config)
    if table is None:
        return [], 0

    session_type_values = tuple(
        _normalize_session_type(candidate)
        for candidate in (
            session_type
            if isinstance(session_type, tuple)
            else ((session_type,) if session_type is not None else (SessionType.TEAM, SessionType.AGENT))
        )
        if candidate is not None
    )
    component_ids = (
        tuple(str(item).strip() for item in component_id if str(item).strip())
        if isinstance(component_id, tuple)
        else ((str(component_id).strip(),) if str(component_id or "").strip() else ())
    )

    filters = [_tenant_client_filter(table, resolved_client_id)]
    if session_type_values:
        filters.append(table.c.session_type.in_(session_type_values))

    resolved_limit = max(1, int(limit or 1))
    resolved_offset = max(0, int(offset or 0))

    with sync_engine.connect() as connection:
        rows = []
        total_count = 0
        for session_type_value in session_type_values or (SessionType.TEAM.value, SessionType.AGENT.value):
            type_filters = [*filters, table.c.session_type == session_type_value]
            component_filter = _session_component_filter(table, session_type_value, component_ids)
            if component_filter is not None:
                type_filters.append(component_filter)
            type_total = connection.execute(select(func.count()).select_from(table).where(*type_filters)).scalar_one()
            total_count += int(type_total or 0)
            type_rows = (
                connection.execute(
                    select(table)
                    .where(*type_filters)
                    .order_by(table.c.created_at.desc(), table.c.updated_at.desc())
                    .limit(resolved_limit)
                    .offset(resolved_offset)
                )
                .mappings()
                .all()
            )
            rows.extend(dict(row) for row in type_rows)

    rows.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("created_at") or "")), reverse=True)
    rows = rows[:resolved_limit]

    return rows, int(total_count or 0)


def get_tenant_conversation_session(
    client_id: str,
    session_id: str,
    *,
    session_type: str | SessionType | tuple[str | SessionType, ...] | None = None,
    component_id: str | tuple[str, ...] | None = _DEFAULT_CONVERSATION_COMPONENT_IDS,
    config: AgnoStorageConfig | None = None,
) -> dict[str, Any] | None:
    resolved_client_id = str(client_id or "").strip()
    resolved_session_id = str(session_id or "").strip()
    if not resolved_client_id or not resolved_session_id:
        return None

    table = _resolve_session_table(config)
    if table is None:
        return None

    with sync_engine.connect() as connection:
        session_type_values = tuple(
            _normalize_session_type(candidate)
            for candidate in (
                session_type
                if isinstance(session_type, tuple)
                else ((session_type,) if session_type is not None else (SessionType.TEAM, SessionType.AGENT))
            )
            if candidate is not None
        )
        component_ids = (
            tuple(str(item).strip() for item in component_id if str(item).strip())
            if isinstance(component_id, tuple)
            else ((str(component_id).strip(),) if str(component_id or "").strip() else ())
        )
        row = None
        for session_type_value in session_type_values or (SessionType.TEAM.value, SessionType.AGENT.value):
            filters = [
                table.c.session_id == resolved_session_id,
                table.c.session_type == session_type_value,
                _tenant_client_filter(table, resolved_client_id),
            ]
            component_filter = _session_component_filter(table, session_type_value, component_ids)
            if component_filter is not None:
                filters.append(component_filter)
            row = connection.execute(select(table).where(*filters).limit(1)).mappings().first()
            if row is not None:
                break

    return dict(row) if row is not None else None


__all__ = [
    "AgnoStorageConfig",
    "aget_session_usage_totals",
    "build_agno_session_kwargs",
    "extract_run_usage_metrics",
    "get_agno_db",
    "get_agno_storage_config",
    "get_async_agno_db",
    "get_session_usage_totals",
    "get_tenant_conversation_session",
    "log_agno_run_metrics",
    "list_tenant_conversation_sessions",
    "resolve_agno_session_id",
]
