"""Tests for assistant turn event logging service."""

from __future__ import annotations

import types

from app.services.assistant_turn_event_service import record_assistant_turn_event


def test_record_assistant_turn_event_is_best_effort(monkeypatch) -> None:
    class BrokenSession:
        def __enter__(self):
            raise RuntimeError("db unavailable")

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("app.services.assistant_turn_event_service.SessionLocal", lambda: BrokenSession())

    # Should not raise
    record_assistant_turn_event(
        client_id="springfield",
        payload={
            "assistant_turn": {"intent_type": "general_zoning", "jurisdiction_status": "not_applicable"},
            "policy_decision": {"decision": "allow", "reason_code": "in_scope"},
        },
    )


def test_record_assistant_turn_event_persists_when_session_available(monkeypatch) -> None:
    captured = {"added": None, "committed": False}

    class FakeDb:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def scalar(self, stmt):
            return types.SimpleNamespace(id="tenant-1")

        def add(self, event):
            captured["added"] = event

        def commit(self):
            captured["committed"] = True

    monkeypatch.setattr("app.services.assistant_turn_event_service.SessionLocal", lambda: FakeDb())

    record_assistant_turn_event(
        client_id="springfield",
        payload={
            "assistant_turn": {"intent_type": "general_zoning", "jurisdiction_status": "not_applicable"},
            "policy_decision": {"decision": "allow", "reason_code": "in_scope"},
            "conversation_id": "conv-1",
        },
    )

    assert captured["added"] is not None
    assert captured["committed"] is True
