"""Tests for public assistant metrics endpoint helper behavior."""

from __future__ import annotations

from app.api.v1.public import get_assistant_metrics
from app.core.security import AuthContext


class _FakeDb:
    def __init__(self):
        self._scalar_calls = 0

    def scalar(self, stmt):
        self._scalar_calls += 1
        if self._scalar_calls == 1:
            return 5
        if self._scalar_calls == 2:
            return 3
        return None

    def execute(self, stmt):
        # First execute is decisions, second is reasons.
        if "policy_decision" in str(stmt):
            return [("allow", 4), ("deny", 1)]
        return [("in_scope", 4), ("non_zoning_scope", 1)]


def test_get_assistant_metrics_returns_aggregates_without_client_filter() -> None:
    payload = get_assistant_metrics(
        client_id=None,
        db=_FakeDb(),
        auth=AuthContext(user_id="user-1", session_id="session-1", provider="clerk"),
    )
    assert payload["total_turns"] == 5
    assert payload["total_feedback"] == 3
    assert payload["decisions"]["allow"] == 4
    assert payload["reason_codes"]["in_scope"] == 4


def test_get_assistant_metrics_raises_when_client_missing(monkeypatch) -> None:
    class FakeDb(_FakeDb):
        def scalar(self, stmt):
            if "tenant_clients" in str(stmt):
                return None
            return super().scalar(stmt)

    try:
        get_assistant_metrics(
            client_id="missing-client",
            db=FakeDb(),
            auth=AuthContext(user_id="user-1", session_id="session-1", provider="clerk"),
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:  # pragma: no cover
        raise AssertionError("Expected 404 when tenant client does not exist")


def test_get_assistant_metrics_requires_authentication() -> None:
    try:
        get_assistant_metrics(client_id=None, db=_FakeDb(), auth=None)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401
    else:  # pragma: no cover
        raise AssertionError("Expected 401 when auth context is missing")
