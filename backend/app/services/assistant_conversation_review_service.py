"""Conversation review helpers for assistant observability data."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, inspect, or_, select

from app.db.models import AssistantMessageFeedback, AssistantRunTelemetry, AssistantTurnEvent, TenantClient
from app.db.session import SessionLocal


_MAX_OBSERVABILITY_STRING_PREVIEW = 300
_MAX_OBSERVABILITY_LIST_ITEMS = 8
_MAX_OBSERVABILITY_DICT_ITEMS = 20
_MAX_OBSERVABILITY_DEPTH = 4


def _truncate_string(value: str, *, limit: int = _MAX_OBSERVABILITY_STRING_PREVIEW) -> dict[str, Any] | str:
    if len(value) <= limit:
        return value
    return {
        "_truncated": True,
        "_type": "string",
        "chars": len(value),
        "preview": value[:limit],
    }


def _summarize_gridics_body(body: str) -> dict[str, Any]:
    return {
        "_truncated": True,
        "_type": "gridics_response_body",
        "chars": len(body),
        "preview": body[:_MAX_OBSERVABILITY_STRING_PREVIEW],
    }


def _summarize_gridics_record(data_row: dict[str, Any]) -> dict[str, Any]:
    buildings = data_row.get("Buildings") if isinstance(data_row, dict) else None
    first_building = buildings[0] if isinstance(buildings, list) and buildings and isinstance(buildings[0], dict) else {}
    envelope = first_building.get("Envelope") if isinstance(first_building, dict) else {}
    zoning_allowance = first_building.get("ZoningAllowance") if isinstance(first_building, dict) else {}
    return {
        "Address": data_row.get("Address"),
        "City": data_row.get("City"),
        "State": data_row.get("State"),
        "ZipCode": data_row.get("ZipCode"),
        "FolioNumber": data_row.get("FolioNumber"),
        "CalculationStatus": data_row.get("CalculationStatus"),
        "LotType": data_row.get("LotType"),
        "ZoneCombinationName": zoning_allowance.get("ZoneCombinationName") if isinstance(zoning_allowance, dict) else None,
        "ZoneId": zoning_allowance.get("ZoneId") if isinstance(zoning_allowance, dict) else None,
        "ZoneTypeId": (
            str(zoning_allowance.get("ZoneTypeId"))
            if isinstance(zoning_allowance, dict) and zoning_allowance.get("ZoneTypeId") is not None
            else None
        ),
        "OverlayCount": len(first_building.get("Overlays") or []) if isinstance(first_building, dict) else 0,
        "UseCount": len(first_building.get("Uses") or []) if isinstance(first_building, dict) else 0,
        "Envelope": {
            "LotAreaFeet": envelope.get("LotAreaFeet") if isinstance(envelope, dict) else None,
            "LotAreaAcres": envelope.get("LotAreaAcres") if isinstance(envelope, dict) else None,
            "DensityUnits": envelope.get("DensityUnits") if isinstance(envelope, dict) else None,
            "FloorAreaRatio": envelope.get("FloorAreaRatio") if isinstance(envelope, dict) else None,
            "MaxBuildingAreaAllowed": envelope.get("MaxBuildingAreaAllowed") if isinstance(envelope, dict) else None,
            "PrincipalMaxHeight": envelope.get("PrincipalMaxHeight") if isinstance(envelope, dict) else None,
            "TotalBuildingHeightFeet": envelope.get("TotalBuildingHeightFeet") if isinstance(envelope, dict) else None,
        },
    }


def _compact_gridics_call_log(entry: dict[str, Any]) -> dict[str, Any]:
    request = entry.get("request") if isinstance(entry, dict) else {}
    response = entry.get("response") if isinstance(entry, dict) else {}
    compact_response: dict[str, Any] = {}
    if isinstance(response, dict):
        compact_response["received"] = response.get("received")
        compact_response["status_code"] = response.get("status_code")
        if "response_length" in response:
            compact_response["response_length"] = response.get("response_length")
        response_json = response.get("json")
        if isinstance(response_json, dict):
            data = response_json.get("data")
            compact_response["json"] = {
                "status": response_json.get("status"),
                "searchType": response_json.get("searchType"),
                "dataRows": response_json.get("dataRows"),
                "data": [_summarize_gridics_record(data[0])] if isinstance(data, list) and data and isinstance(data[0], dict) else [],
            }
    return {
        "request": {
            "method": request.get("method"),
            "url": request.get("url"),
            "path": request.get("path"),
            "params": request.get("params"),
        }
        if isinstance(request, dict)
        else request,
        "response": compact_response,
    }


def _compact_observability_value(value: Any, *, depth: int = 0) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _truncate_string(value)
    if depth >= _MAX_OBSERVABILITY_DEPTH:
        if isinstance(value, dict):
            return {"_truncated": True, "_type": "object", "keys": list(value.keys())[:_MAX_OBSERVABILITY_DICT_ITEMS]}
        if isinstance(value, list):
            return {"_truncated": True, "_type": "array", "items": len(value)}
        return value
    if isinstance(value, list):
        compacted = [_compact_observability_value(item, depth=depth + 1) for item in value[:_MAX_OBSERVABILITY_LIST_ITEMS]]
        if len(value) > _MAX_OBSERVABILITY_LIST_ITEMS:
            compacted.append(
                {
                    "_truncated": True,
                    "_type": "array",
                    "items": len(value),
                    "omitted": len(value) - _MAX_OBSERVABILITY_LIST_ITEMS,
                }
            )
        return compacted
    if isinstance(value, dict):
        if "gridics_call_log" in value and isinstance(value.get("gridics_call_log"), list):
            compacted = dict(value)
            compacted["gridics_call_log"] = [
                _compact_gridics_call_log(item)
                for item in value.get("gridics_call_log", [])[:_MAX_OBSERVABILITY_LIST_ITEMS]
                if isinstance(item, dict)
            ]
            if len(value.get("gridics_call_log", [])) > _MAX_OBSERVABILITY_LIST_ITEMS:
                compacted["gridics_call_log"].append(
                    {
                        "_truncated": True,
                        "_type": "array",
                        "items": len(value["gridics_call_log"]),
                        "omitted": len(value["gridics_call_log"]) - _MAX_OBSERVABILITY_LIST_ITEMS,
                    }
                )
            return compacted

        compacted: dict[str, Any] = {}
        for key, item in list(value.items())[:_MAX_OBSERVABILITY_DICT_ITEMS]:
            if key == "body" and isinstance(item, str):
                compacted[key] = _truncate_string(item)
            elif key == "json" and isinstance(item, dict):
                compacted[key] = _compact_observability_value(item, depth=depth + 1)
            else:
                compacted[key] = _compact_observability_value(item, depth=depth + 1)
        if len(value) > _MAX_OBSERVABILITY_DICT_ITEMS:
            compacted["_truncated"] = True
            compacted["_type"] = "object"
            compacted["_omitted_keys"] = list(value.keys())[_MAX_OBSERVABILITY_DICT_ITEMS:]
        return compacted
    return value


def _compact_turn_payload(payload: dict[str, Any]) -> dict[str, Any]:
    compacted = _compact_observability_value(payload)
    return compacted if isinstance(compacted, dict) else {"payload": compacted}


def _has_conversation_review_storage(db) -> bool:
    bind = db.get_bind()
    if bind is None:
        return False
    try:
        inspector = inspect(bind)
    except Exception:
        return False
    return all(
        inspector.has_table(table_name)
        for table_name in (
            "agentic_assistant_turn_events",
            "agentic_assistant_run_telemetry",
            "agentic_assistant_message_feedback",
        )
    )


def _empty_review_payload() -> dict[str, Any]:
    return {
        "summary": {
            "total_conversations": 0,
            "total_turns": 0,
            "total_runs": 0,
            "total_feedback": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
        },
        "conversations": [],
        "pagination": {
            "page": 1,
            "page_size": 20,
            "total_conversations": 0,
            "total_pages": 0,
            "has_previous": False,
            "has_next": False,
            "search": None,
            "conversation_id": None,
        },
    }


def _coerce_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float, Decimal)):
        try:
            return float(value)
        except Exception:
            return 0.0
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except Exception:
            return 0.0
    return 0.0


def _normalize_filter_term(value: str | None) -> str:
    return (value or "").strip().lower()


def _conversation_search_clause(search_term: str):
    pattern = f"%{search_term}%"
    return or_(
        func.lower(func.coalesce(AssistantTurnEvent.conversation_id, "")).like(pattern),
        func.lower(func.coalesce(AssistantTurnEvent.message_id, "")).like(pattern),
        func.lower(func.coalesce(AssistantTurnEvent.run_id, "")).like(pattern),
        func.lower(func.coalesce(AssistantTurnEvent.agent_id, "")).like(pattern),
        func.lower(func.coalesce(AssistantTurnEvent.intent_type, "")).like(pattern),
        func.lower(func.coalesce(AssistantTurnEvent.jurisdiction_status, "")).like(pattern),
        func.lower(func.coalesce(AssistantTurnEvent.policy_decision, "")).like(pattern),
        func.lower(func.coalesce(AssistantTurnEvent.reason_code, "")).like(pattern),
    )


def _telemetry_search_clause(search_term: str):
    pattern = f"%{search_term}%"
    return or_(
        func.lower(func.coalesce(AssistantRunTelemetry.conversation_id, "")).like(pattern),
        func.lower(func.coalesce(AssistantRunTelemetry.session_id, "")).like(pattern),
        func.lower(func.coalesce(AssistantRunTelemetry.run_id, "")).like(pattern),
        func.lower(func.coalesce(AssistantRunTelemetry.agent_id, "")).like(pattern),
        func.lower(func.coalesce(AssistantRunTelemetry.model_id, "")).like(pattern),
        func.lower(func.coalesce(AssistantRunTelemetry.model_name, "")).like(pattern),
        func.lower(func.coalesce(AssistantRunTelemetry.model_provider, "")).like(pattern),
    )


def _feedback_search_clause(search_term: str):
    pattern = f"%{search_term}%"
    return or_(
        func.lower(func.coalesce(AssistantMessageFeedback.conversation_id, "")).like(pattern),
        func.lower(func.coalesce(AssistantMessageFeedback.message_id, "")).like(pattern),
        func.lower(func.coalesce(AssistantMessageFeedback.run_id, "")).like(pattern),
        func.lower(func.coalesce(AssistantMessageFeedback.agent_id, "")).like(pattern),
        func.lower(func.coalesce(AssistantMessageFeedback.feedback_value, "")).like(pattern),
        func.lower(func.coalesce(AssistantMessageFeedback.message_excerpt, "")).like(pattern),
    )


def _collect_matching_conversation_ids(db, tenant_id: str, search_term: str) -> set[str]:
    matching_conversation_ids: set[str] = set()

    turn_stmt = select(AssistantTurnEvent.conversation_id).where(AssistantTurnEvent.tenant_client_id == tenant_id)
    telemetry_stmt = select(AssistantRunTelemetry.conversation_id).where(
        AssistantRunTelemetry.tenant_client_id == tenant_id
    )
    feedback_stmt = select(AssistantMessageFeedback.conversation_id).where(
        AssistantMessageFeedback.tenant_client_id == tenant_id
    )

    if search_term:
        turn_stmt = turn_stmt.where(_conversation_search_clause(search_term))
        telemetry_stmt = telemetry_stmt.where(_telemetry_search_clause(search_term))
        feedback_stmt = feedback_stmt.where(_feedback_search_clause(search_term))

    for statement in (turn_stmt, telemetry_stmt, feedback_stmt):
        for conversation_id in db.scalars(statement.distinct()).all():
            normalized = str(conversation_id or "").strip()
            if normalized:
                matching_conversation_ids.add(normalized)

    return matching_conversation_ids


def _build_conversation_group(
    *,
    conversation_id: str,
    turns: list[AssistantTurnEvent],
    runs: list[AssistantRunTelemetry],
    feedback: list[AssistantMessageFeedback],
) -> dict[str, Any]:
    turn_rows = [
        {
            "id": row.id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "message_id": row.message_id,
            "run_id": row.run_id,
            "agent_id": row.agent_id,
            "intent_type": row.intent_type,
            "jurisdiction_status": row.jurisdiction_status,
            "policy_decision": row.policy_decision,
            "reason_code": row.reason_code,
            "payload_json": _compact_turn_payload(row.payload_json or {}),
        }
        for row in sorted(turns, key=lambda row: row.created_at or datetime.min)
    ]

    run_rows = [
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
            "metrics_json": _compact_observability_value(row.metrics_json or {}),
        }
        for row in sorted(runs, key=lambda row: row.created_at or datetime.min, reverse=True)
    ]

    feedback_rows = [
        {
            "id": row.id,
            "clerk_user_id": row.clerk_user_id,
            "agent_id": row.agent_id,
            "surface": row.surface,
            "conversation_id": row.conversation_id,
            "message_id": row.message_id,
            "run_id": row.run_id,
            "feedback_value": row.feedback_value,
            "message_excerpt": row.message_excerpt,
            "metadata_json": _compact_observability_value(row.metadata_json or {}),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in sorted(feedback, key=lambda row: row.created_at or datetime.min, reverse=True)
    ]

    total_input_tokens = sum(row["input_tokens"] for row in run_rows)
    total_output_tokens = sum(row["output_tokens"] for row in run_rows)
    total_tokens = sum(row["total_tokens"] for row in run_rows)
    total_cost = sum(_coerce_float(row["cost"]) for row in run_rows)

    latest_at = None
    if turn_rows:
        latest_at = turn_rows[-1]["created_at"]
    elif run_rows:
        latest_at = run_rows[0]["created_at"]
    elif feedback_rows:
        latest_at = feedback_rows[0]["created_at"]

    return {
        "conversation_id": conversation_id,
        "latest_at": latest_at,
        "turn_count": len(turn_rows),
        "run_count": len(run_rows),
        "feedback_count": len(feedback_rows),
        "input_tokens": int(total_input_tokens),
        "output_tokens": int(total_output_tokens),
        "total_tokens": int(total_tokens),
        "cost": float(total_cost),
        "turns": turn_rows,
        "runs": run_rows,
        "feedback": feedback_rows,
    }


def list_assistant_conversation_reviews(
    *,
    client_id: str | None,
    limit: int = 20,
    page: int = 1,
    search: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    with SessionLocal() as db:
        if not _has_conversation_review_storage(db):
            return _empty_review_payload()
        tenant = db.scalar(select(TenantClient).where(TenantClient.client_id == (client_id or "").strip()))
        if tenant is None:
            return _empty_review_payload()

        page = max(1, int(page or 1))
        page_size = max(1, min(limit, 100))
        search_term = _normalize_filter_term(search)
        requested_conversation_id = (conversation_id or "").strip() or None

        matching_conversation_ids = _collect_matching_conversation_ids(db, tenant.id, search_term)
        if requested_conversation_id is not None:
            matching_conversation_ids = {requested_conversation_id}
        if not matching_conversation_ids:
            return _empty_review_payload()

        turn_rows = db.scalars(
            select(AssistantTurnEvent)
            .where(
                AssistantTurnEvent.tenant_client_id == tenant.id,
                AssistantTurnEvent.conversation_id.in_(sorted(matching_conversation_ids)),
            )
            .order_by(AssistantTurnEvent.created_at.asc())
        ).all()
        run_rows = db.scalars(
            select(AssistantRunTelemetry)
            .where(
                AssistantRunTelemetry.tenant_client_id == tenant.id,
                AssistantRunTelemetry.conversation_id.in_(sorted(matching_conversation_ids)),
            )
            .order_by(AssistantRunTelemetry.created_at.desc())
        ).all()
        feedback_rows = db.scalars(
            select(AssistantMessageFeedback)
            .where(
                AssistantMessageFeedback.tenant_client_id == tenant.id,
                AssistantMessageFeedback.conversation_id.in_(sorted(matching_conversation_ids)),
            )
            .order_by(AssistantMessageFeedback.created_at.desc())
        ).all()

        grouped_turns: dict[str, list[AssistantTurnEvent]] = defaultdict(list)
        for row in turn_rows:
            normalized_conversation_id = str(row.conversation_id or "").strip()
            if normalized_conversation_id:
                grouped_turns[normalized_conversation_id].append(row)

        grouped_runs: dict[str, list[AssistantRunTelemetry]] = defaultdict(list)
        for row in run_rows:
            normalized_conversation_id = str(row.conversation_id or "").strip()
            if normalized_conversation_id:
                grouped_runs[normalized_conversation_id].append(row)

        grouped_feedback: dict[str, list[AssistantMessageFeedback]] = defaultdict(list)
        for row in feedback_rows:
            normalized_conversation_id = str(row.conversation_id or "").strip()
            if normalized_conversation_id:
                grouped_feedback[normalized_conversation_id].append(row)

        conversation_ids = sorted(
            {
                *grouped_turns.keys(),
                *grouped_runs.keys(),
                *grouped_feedback.keys(),
            },
            key=lambda item: item.lower(),
        )

        conversation_summaries: list[dict[str, Any]] = []
        for cid in conversation_ids:
            conversation_summaries.append(
                _build_conversation_group(
                    conversation_id=cid,
                    turns=grouped_turns.get(cid, []),
                    runs=grouped_runs.get(cid, []),
                    feedback=grouped_feedback.get(cid, []),
                )
            )

        # Sort by latest activity before pagination, then page the conversations.
        conversation_summaries.sort(key=lambda item: item.get("latest_at") or "", reverse=True)
        total_conversations = len(conversation_summaries)
        total_pages = max(1, (total_conversations + page_size - 1) // page_size) if total_conversations else 0
        page = min(page, total_pages or 1)
        offset = (page - 1) * page_size
        paged_conversations = conversation_summaries[offset : offset + page_size]

        total_turns = sum(conversation["turn_count"] for conversation in conversation_summaries)
        total_runs = sum(conversation["run_count"] for conversation in conversation_summaries)
        total_feedback = sum(conversation["feedback_count"] for conversation in conversation_summaries)
        total_input_tokens = sum(conversation["input_tokens"] for conversation in conversation_summaries)
        total_output_tokens = sum(conversation["output_tokens"] for conversation in conversation_summaries)
        total_total_tokens = sum(conversation["total_tokens"] for conversation in conversation_summaries)
        total_cost = sum(_coerce_float(conversation["cost"]) for conversation in conversation_summaries)

        return {
            "summary": {
                "total_conversations": int(total_conversations),
                "total_turns": int(total_turns),
                "total_runs": int(total_runs),
                "total_feedback": int(total_feedback),
                "input_tokens": int(total_input_tokens),
                "output_tokens": int(total_output_tokens),
                "total_tokens": int(total_total_tokens),
                "cost": float(total_cost),
            },
            "conversations": paged_conversations,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_conversations": total_conversations,
                "total_pages": total_pages,
                "has_previous": page > 1 and total_conversations > 0,
                "has_next": page < total_pages,
                "search": search_term or None,
                "conversation_id": requested_conversation_id,
            },
        }
