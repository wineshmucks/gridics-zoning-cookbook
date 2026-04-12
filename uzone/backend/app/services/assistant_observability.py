"""Lightweight assistant observability helpers for policy and routing traces."""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any


def append_policy_trace(run_context: Any, event: dict[str, Any]) -> None:
    """Attach structured policy events to run metadata for later inspection."""
    metadata = getattr(run_context, "metadata", None)
    if not isinstance(metadata, dict):
        return

    trace = metadata.get("policy_trace")
    if not isinstance(trace, list):
        trace = []
        metadata["policy_trace"] = trace

    payload = dict(event)
    payload.setdefault("timestamp", datetime.now(UTC).isoformat())
    trace.append(payload)
