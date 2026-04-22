"""Route coverage for super-admin Agno trace APIs."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.api.v1 import admin


def test_agno_trace_routes(monkeypatch) -> None:
    calls: dict[str, object] = {}

    trace = SimpleNamespace(
        trace_id="trace-1",
        name="assistant.run",
        status="OK",
        start_time=datetime(2026, 4, 22, 10, 0, tzinfo=UTC),
        end_time=datetime(2026, 4, 22, 10, 0, 5, tzinfo=UTC),
        duration_ms=5000,
        total_spans=2,
        error_count=0,
        run_id="run-1",
        session_id="session-1",
        user_id="user-1",
        agent_id="agent-1",
        team_id="team-1",
        workflow_id=None,
        created_at=datetime(2026, 4, 22, 10, 0, 6, tzinfo=UTC),
    )
    span = SimpleNamespace(
        span_id="span-1",
        trace_id="trace-1",
        parent_span_id=None,
        name="assistant.run",
        span_kind="INTERNAL",
        status_code="OK",
        status_message=None,
        start_time=datetime(2026, 4, 22, 10, 0, tzinfo=UTC),
        end_time=datetime(2026, 4, 22, 10, 0, 5, tzinfo=UTC),
        duration_ms=5000,
        attributes={"session_id": "session-1"},
        created_at=datetime(2026, 4, 22, 10, 0, 6, tzinfo=UTC),
    )

    class FakeAgnoDb:
        def get_traces(self, **kwargs):
            calls["list"] = kwargs
            return [trace], 1

        def get_trace(self, **kwargs):
            calls["detail"] = kwargs
            return trace

        def get_spans(self, **kwargs):
            calls["spans"] = kwargs
            return [span]

    monkeypatch.setattr(admin, "get_agno_db", lambda: FakeAgnoDb())

    listed = admin.list_agno_traces_route(session_id="session-1", trace_status="ok", limit=25, page=1)
    assert calls["list"] == {
        "session_id": "session-1",
        "run_id": None,
        "status": "OK",
        "limit": 25,
        "page": 1,
    }
    assert listed.total_count == 1
    assert listed.items[0].trace_id == "trace-1"
    assert listed.items[0].session_id == "session-1"

    detail = admin.get_agno_trace_route("trace-1")
    assert calls["detail"] == {"trace_id": "trace-1"}
    assert calls["spans"] == {"trace_id": "trace-1", "limit": 1000}
    assert detail.trace.trace_id == "trace-1"
    assert detail.spans[0].span_id == "span-1"
