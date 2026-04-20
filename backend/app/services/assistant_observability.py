"""Lightweight assistant observability helpers for policy and routing traces."""

from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import Any


logger = logging.getLogger(__name__)


def _resolve_trace_metadata(run_context: Any) -> dict[str, Any] | None:
    if isinstance(run_context, dict):
        return run_context

    metadata = getattr(run_context, "metadata", None)
    if isinstance(metadata, dict):
        return metadata

    return None


def append_run_trace(run_context: Any, event: dict[str, Any]) -> None:
    """Attach a structured run trace event to metadata for later inspection."""
    metadata = _resolve_trace_metadata(run_context)
    if metadata is None:
        return

    trace = metadata.get("run_trace")
    if not isinstance(trace, list):
        trace = []
        metadata["run_trace"] = trace

    payload = dict(event)
    payload.setdefault("timestamp", datetime.now(UTC).isoformat())
    trace.append(payload)
    logger.debug("assistant run trace event=%s", payload.get("event") or payload.get("kind"))


def get_run_trace(run_context: Any) -> list[dict[str, Any]]:
    metadata = _resolve_trace_metadata(run_context)
    if metadata is None:
        return []

    trace = metadata.get("run_trace")
    if not isinstance(trace, list):
        return []
    return [event for event in trace if isinstance(event, dict)]


def append_policy_trace(run_context: Any, event: dict[str, Any]) -> None:
    """Attach structured policy events to run metadata for later inspection."""
    metadata = _resolve_trace_metadata(run_context)
    if metadata is None:
        return

    trace = metadata.get("policy_trace")
    if not isinstance(trace, list):
        trace = []
        metadata["policy_trace"] = trace

    payload = dict(event)
    payload.setdefault("timestamp", datetime.now(UTC).isoformat())
    trace.append(payload)
    append_run_trace(metadata, {"kind": "policy", **payload})
