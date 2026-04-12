"""Tests for assistant policy trace observability helpers."""

from __future__ import annotations

import types

from app.services.assistant_observability import append_policy_trace


def test_append_policy_trace_adds_events_to_metadata() -> None:
    run_context = types.SimpleNamespace(metadata={})
    append_policy_trace(
        run_context,
        {"decision": "allow", "reason_code": "in_scope"},
    )
    assert isinstance(run_context.metadata.get("policy_trace"), list)
    assert run_context.metadata["policy_trace"][0]["decision"] == "allow"
    assert run_context.metadata["policy_trace"][0]["reason_code"] == "in_scope"
    assert "timestamp" in run_context.metadata["policy_trace"][0]
