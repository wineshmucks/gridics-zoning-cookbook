from __future__ import annotations

from types import SimpleNamespace

import app.agents.customer_zoning_agent as customer_zoning_agent
import app.agents.storage as agno_storage


def test_build_agno_session_kwargs_caps_history_and_warns(monkeypatch, caplog) -> None:
    monkeypatch.setattr(agno_storage.settings, "agno_sessions_enabled", True, raising=False)
    monkeypatch.setattr(agno_storage.settings, "agno_session_table", "custom_sessions", raising=False)
    monkeypatch.setattr(agno_storage.settings, "agno_store_history_messages", True, raising=False)
    monkeypatch.setattr(agno_storage.settings, "agno_num_history_runs", 99, raising=False)

    caplog.set_level("WARNING")
    kwargs = agno_storage.build_agno_session_kwargs()

    assert kwargs["db"] is not None
    assert kwargs["add_history_to_context"] is True
    assert kwargs["num_history_runs"] == 5
    assert kwargs["store_history_messages"] is True
    assert "full history messages" in caplog.text


def test_get_async_agno_db_builds_async_postgres_db(monkeypatch) -> None:
    monkeypatch.setattr(agno_storage.settings, "agno_sessions_enabled", True, raising=False)
    async_db = agno_storage.get_async_agno_db()

    assert async_db is not None
    assert async_db.__class__.__name__ == "AsyncPostgresDb"


def test_resolve_agno_session_id_prefers_existing_conversation_identity() -> None:
    run_context = SimpleNamespace(metadata={"conversation_id": "conv-123", "thread_id": "thread-999"})

    assert agno_storage.resolve_agno_session_id(run_context=run_context) == "conv-123"
    assert agno_storage.resolve_agno_session_id(metadata={"chat_id": "chat-456"}) == "chat-456"


def test_get_session_usage_totals_sums_runs_and_model_usage(monkeypatch) -> None:
    run_one = SimpleNamespace(
        metrics=SimpleNamespace(
            input_tokens=10,
            output_tokens=6,
            total_tokens=16,
            reasoning_tokens=2,
            cache_read_tokens=1,
            cache_write_tokens=0,
            cost=0.12,
            time_to_first_token=0.4,
            duration=2.5,
            details={
                "model": [
                    SimpleNamespace(
                        provider="gemini",
                        id="gemini-2.5-flash-lite",
                        input_tokens=10,
                        output_tokens=6,
                        total_tokens=16,
                        reasoning_tokens=2,
                        cache_read_tokens=1,
                        cache_write_tokens=0,
                        cost=0.12,
                    )
                ]
            },
        )
    )
    run_two = SimpleNamespace(
        metrics=SimpleNamespace(
            input_tokens=4,
            output_tokens=3,
            total_tokens=7,
            reasoning_tokens=1,
            cache_read_tokens=0,
            cache_write_tokens=0,
            cost=0.03,
            time_to_first_token=0.2,
            duration=1.0,
            details={
                "model": [
                    SimpleNamespace(
                        provider="gemini",
                        id="gemini-2.5-flash-lite",
                        input_tokens=4,
                        output_tokens=3,
                        total_tokens=7,
                        reasoning_tokens=1,
                        cache_read_tokens=0,
                        cache_write_tokens=0,
                        cost=0.03,
                    )
                ]
            },
        )
    )
    session = SimpleNamespace(session_id="session-abc", session_type="team", runs=[run_one, run_two])
    calls: list[tuple[str, str]] = []

    class FakeDb:
        def get_session(self, *, session_id: str, session_type: str, user_id=None, deserialize=True):
            calls.append((session_id, session_type))
            return session if session_type == "team" else None

    summary = agno_storage.get_session_usage_totals("session-abc", db=FakeDb())

    assert calls[0] == ("session-abc", "team")
    assert summary is not None
    assert summary["session_id"] == "session-abc"
    assert summary["session_type"] == "team"
    assert summary["run_count"] == 2
    assert summary["totals"]["input_tokens"] == 14
    assert summary["totals"]["output_tokens"] == 9
    assert summary["totals"]["total_tokens"] == 23
    assert summary["totals"]["reasoning_tokens"] == 3
    assert summary["totals"]["cache_read_tokens"] == 1
    assert summary["totals"]["cost"] == 0.15
    assert summary["totals"]["duration"] == 3.5
    assert summary["totals"]["time_to_first_token_max"] == 0.4
    assert summary["model_usage"] == [
        {
            "kind": "model",
            "provider": "gemini",
            "model_id": "gemini-2.5-flash-lite",
            "input_tokens": 14,
            "output_tokens": 9,
            "total_tokens": 23,
            "reasoning_tokens": 3,
            "cache_read_tokens": 1,
            "cache_write_tokens": 0,
            "cost": 0.15,
        }
    ]


def test_customer_zoning_construction_uses_shared_agno_session_kwargs(monkeypatch) -> None:
    monkeypatch.setattr(
        customer_zoning_agent,
        "AGNO_SESSION_KWARGS",
        {
            "db": "shared-db",
            "add_history_to_context": True,
            "num_history_runs": 4,
            "store_history_messages": False,
        },
        raising=False,
    )
    monkeypatch.setattr(customer_zoning_agent, "_build_default_agent_model", lambda target_id: f"model:{target_id}")
    monkeypatch.setattr(customer_zoning_agent, "_coerce_agno_model", lambda model: model)

    team_captured: dict[str, object] = {}
    agent_captured: dict[str, object] = {}

    def fake_team(**kwargs):
        team_captured.update(kwargs)
        return kwargs

    def fake_agent(**kwargs):
        agent_captured.update(kwargs)
        return kwargs

    monkeypatch.setattr(customer_zoning_agent, "Team", fake_team)
    monkeypatch.setattr(customer_zoning_agent, "create_agent", fake_agent)

    team = customer_zoning_agent.build_customer_zoning_team()
    agent = customer_zoning_agent.build_customer_zoning_agent()

    assert team == team_captured
    assert agent == agent_captured
    assert team_captured["db"] == "shared-db"
    assert team_captured["add_history_to_context"] is True
    assert team_captured["num_history_runs"] == 4
    assert team_captured["store_history_messages"] is False
    assert team_captured["post_hooks"] == [customer_zoning_agent.log_agno_run_metrics]
    assert agent_captured["db"] == "shared-db"
    assert agent_captured["add_history_to_context"] is True
    assert agent_captured["num_history_runs"] == 4
    assert agent_captured["store_history_messages"] is False
    assert agent_captured["post_hooks"] == [customer_zoning_agent.log_agno_run_metrics]
