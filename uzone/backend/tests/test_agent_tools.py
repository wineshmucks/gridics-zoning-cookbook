"""Tests for Agno zoning tools."""

from __future__ import annotations

import sys
import types

from app.agents.tools import query_customer_zoning_code


class DummyTenant:
    client_id = "springfield"


class DummyRunContext:
    def __init__(self, dependencies: dict[str, object] | None = None) -> None:
        self.dependencies = dependencies


def test_query_customer_zoning_code_uses_run_context_client_id(monkeypatch) -> None:
    tenant = DummyTenant()
    captured: dict[str, object] = {}

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def scalar(self, statement):
            captured["statement"] = statement
            return tenant

    def fake_query_customer_zoning_knowledge(db, tenant_client, *, query: str, limit: int):
        captured["db"] = db
        captured["tenant_client"] = tenant_client
        captured["query"] = query
        captured["limit"] = limit
        return {"query": query, "results": []}

    session_module = types.ModuleType("app.db.session")
    session_module.SessionLocal = lambda: FakeSession()
    monkeypatch.setitem(sys.modules, "app.db.session", session_module)
    monkeypatch.setattr(
        "app.services.zoning_knowledge_service.query_customer_zoning_knowledge",
        fake_query_customer_zoning_knowledge,
    )

    result = query_customer_zoning_code(
        query="What are the height limits?",
        limit=4,
        run_context=DummyRunContext({"client_id": "springfield"}),
    )

    assert result == {"query": "What are the height limits?", "results": []}
    assert captured["tenant_client"] is tenant
    assert captured["query"] == "What are the height limits?"
    assert captured["limit"] == 4


def test_query_customer_zoning_code_requires_client_id_when_unbound() -> None:
    try:
        query_customer_zoning_code(query="Anything here?")
    except ValueError as exc:
        assert "client_id" in str(exc)
    else:  # pragma: no cover - explicit failure branch
        raise AssertionError("Expected ValueError when no client_id is provided")
