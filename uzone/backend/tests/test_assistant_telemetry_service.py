"""Tests for assistant telemetry persistence helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import AssistantRunTelemetry, TenantClient
from app.services.assistant_telemetry_service import list_assistant_run_telemetry, record_assistant_run_telemetry


def test_record_assistant_run_telemetry_extracts_usage_metrics(monkeypatch) -> None:
    captured = {"event": None, "committed": False}

    class FakeDb:
        def add(self, event):
            captured["event"] = event

        def commit(self):
            captured["committed"] = True

    monkeypatch.setattr("app.services.assistant_telemetry_service.SessionLocal", lambda: FakeDb())
    monkeypatch.setattr("app.services.assistant_telemetry_service._has_assistant_run_telemetry_storage", lambda db: True)
    monkeypatch.setattr("app.services.assistant_telemetry_service._resolve_tenant_id", lambda db, client_id: "tenant-1")

    record_assistant_run_telemetry(
        client_id="springfield",
        payload={
            "conversation_id": "conversation-123",
            "session_id": "conversation-123",
            "run_id": "run-789",
            "model_trace": {"provider": "gemini", "model_id": "gemini-2.5-pro", "api_key_source": "tenant_db", "api_key_suffix": "abcd"},
            "run_output": {
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 9,
                    "cost": 0.0125,
                    "duration": 3.4,
                    "time_to_first_token": 0.6,
                },
                "response": {
                    "model": {
                        "provider": "gemini",
                        "model_name": "gemini-2.5-pro",
                        "id": "gemini-2.5-pro",
                    }
                },
            },
        },
    )

    assert captured["committed"] is True
    event = captured["event"]
    assert event is not None
    assert event.tenant_client_id == "tenant-1"
    assert event.conversation_id == "conversation-123"
    assert event.run_id == "run-789"
    assert event.input_tokens == 11
    assert event.output_tokens == 9
    assert event.total_tokens == 20
    assert float(event.cost) == 0.0125
    assert float(event.duration_seconds) == 3.4
    assert event.metrics_json["model_trace"]["api_key_source"] == "tenant_db"


def test_record_assistant_run_telemetry_extracts_metrics_from_plain_objects(monkeypatch) -> None:
    captured = {"event": None}

    class FakeDb:
        def add(self, event):
            captured["event"] = event

        def commit(self):
            pass

    class MetricsObject:
        def __init__(self) -> None:
            self.prompt_tokens = 5
            self.completion_tokens = 7
            self.cost = 0.01
            self.duration = 1.2
            self.time_to_first_token = 0.2

    monkeypatch.setattr("app.services.assistant_telemetry_service.SessionLocal", lambda: FakeDb())
    monkeypatch.setattr("app.services.assistant_telemetry_service._has_assistant_run_telemetry_storage", lambda db: True)
    monkeypatch.setattr("app.services.assistant_telemetry_service._resolve_tenant_id", lambda db, client_id: "tenant-1")

    record_assistant_run_telemetry(
        client_id="springfield",
        payload={
            "conversation_id": "conversation-123",
            "run_output": {
                "metrics": MetricsObject(),
            },
        },
    )

    event = captured["event"]
    assert event is not None
    assert event.input_tokens == 5
    assert event.output_tokens == 7
    assert event.total_tokens == 12
    assert float(event.cost) == 0.01
    assert float(event.duration_seconds) == 1.2


def test_list_assistant_run_telemetry_pages_and_filters_results(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = session_factory()
    try:
        tenant = TenantClient(
            id="tenant-1",
            client_id="springfield",
            city_name="Springfield",
            department_name="Planning",
        )
        db.add(tenant)
        db.commit()

        created_at = datetime.now(UTC).replace(tzinfo=None)
        db.add_all(
            [
                AssistantRunTelemetry(
                    tenant_client_id=tenant.id,
                    run_scope="team",
                    agent_id="customer-zoning-agent",
                    conversation_id="conv-1",
                    run_id="run-1",
                    session_id="session-1",
                    model_provider="gemini",
                    model_name="gemini-2.5-pro",
                    model_id="gemini-2.5-pro",
                    input_tokens=10,
                    output_tokens=20,
                    total_tokens=30,
                    cost=0.05,
                    created_at=created_at - timedelta(minutes=2),
                ),
                AssistantRunTelemetry(
                    tenant_client_id=tenant.id,
                    run_scope="team",
                    agent_id="customer-zoning-agent",
                    conversation_id="conv-2",
                    run_id="run-2",
                    session_id="session-2",
                    model_provider="openai",
                    model_name="gpt-4.1",
                    model_id="gpt-4.1",
                    input_tokens=7,
                    output_tokens=9,
                    total_tokens=16,
                    cost=0.02,
                    created_at=created_at - timedelta(minutes=1),
                ),
            ]
        )
        db.commit()

        monkeypatch.setattr("app.services.assistant_telemetry_service.SessionLocal", session_factory)

        first_page = list_assistant_run_telemetry(client_id="springfield", limit=1, page=1, search="gemini")
        second_page = list_assistant_run_telemetry(client_id="springfield", limit=1, page=2)

        assert first_page["summary"]["total_runs"] == 1
        assert first_page["summary"]["input_tokens"] == 10
        assert first_page["runs"][0]["model_id"] == "gemini-2.5-pro"
        assert first_page["pagination"]["page"] == 1
        assert first_page["pagination"]["page_size"] == 1
        assert first_page["pagination"]["total_runs"] == 1
        assert first_page["pagination"]["total_pages"] == 1
        assert first_page["pagination"]["has_next"] is False

        assert second_page["pagination"]["page"] == 2
        assert second_page["pagination"]["page_size"] == 1
        assert second_page["pagination"]["total_runs"] == 2
        assert second_page["pagination"]["total_pages"] == 2
        assert second_page["pagination"]["has_previous"] is True
        assert len(second_page["runs"]) == 1
    finally:
        db.close()
