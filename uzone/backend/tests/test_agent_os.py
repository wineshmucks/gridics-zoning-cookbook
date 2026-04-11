"""Tests for AgentOS assembly."""

from __future__ import annotations

import sys
import types

from fastapi import FastAPI

from app import agent_os


def test_build_agent_os_db_uses_app_postgres_settings(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakePostgresDb:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.db_url = kwargs["db_url"]
            self.db_schema = kwargs["db_schema"]
            self.session_table_name = kwargs["session_table"]

    monkeypatch.setitem(sys.modules, "agno.db.postgres.postgres", types.SimpleNamespace(PostgresDb=FakePostgresDb))

    db = agent_os._build_agent_os_db()

    assert db.db_url == agent_os.settings.database_url
    assert db.db_schema == "agent_os"
    assert db.session_table_name == "aos_sessions"


def test_build_agent_os_app_configures_persistent_db(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeAgentOS:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def get_app(self):
            app = FastAPI()
            app.state.agent_os_kwargs = captured
            return app

    fake_module = types.SimpleNamespace(AgentOS=FakeAgentOS)
    monkeypatch.setitem(sys.modules, "agno.os", fake_module)
    monkeypatch.setitem(sys.modules, "app.agents.registry", types.SimpleNamespace(ALL_AGENTS=["agent-sentinel"]))
    monkeypatch.setattr(agent_os, "_build_agent_os_db", lambda: "db-sentinel")

    app = agent_os.build_agent_os_app(FastAPI())

    assert app.state.agent_os_kwargs["db"] == "db-sentinel"
    assert app.state.agent_os_kwargs["auto_provision_dbs"] is True
    assert app.state.agent_os_kwargs["telemetry"] is False
    assert app.state.agent_os_kwargs["agents"] == ["agent-sentinel"]
