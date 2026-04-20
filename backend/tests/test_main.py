"""Tests for application assembly."""

from __future__ import annotations

import importlib
import sys
import types

from fastapi import APIRouter


def _load_main_module():
    stub_routes = types.ModuleType("app.api.routes")
    stub_routes.api_router = APIRouter()
    sys.modules["app.api.routes"] = stub_routes
    stub_agent_os = types.ModuleType("app.agent_os")
    stub_agent_os.build_agent_os_app = lambda base_app: base_app
    sys.modules["app.agent_os"] = stub_agent_os
    sys.modules.pop("app.main", None)
    return importlib.import_module("app.main")


def test_create_app_without_agent_os() -> None:
    main = _load_main_module()
    main.settings.enable_agent_os = False

    app = main.create_app()

    paths = {route.path for route in app.routes}

    assert app.state.agent_os_enabled is False
    assert "/health" not in paths
    assert "/agents" not in paths


def test_create_app_with_agent_os(monkeypatch) -> None:
    main = _load_main_module()
    main.settings.enable_agent_os = True
    main.settings.require_agent_os = True

    def fake_build_agent_os_app(base_app):
        base_app.state.agent_os_enabled = True
        return base_app

    monkeypatch.setattr(main, "build_agent_os_app", fake_build_agent_os_app)

    app = main.create_app()

    assert app.state.agent_os_enabled is True


def test_create_app_falls_back_when_agent_os_dependency_missing(monkeypatch) -> None:
    main = _load_main_module()
    main.settings.enable_agent_os = True
    main.settings.require_agent_os = False

    def fake_build_agent_os_app(base_app):
        raise RuntimeError("Agno AgentOS support is not installed in the backend environment.")

    monkeypatch.setattr(main, "build_agent_os_app", fake_build_agent_os_app)

    app = main.create_app()

    assert app.state.agent_os_enabled is False
    assert app.title == main.settings.app_name


def test_create_app_raises_when_agent_os_is_required(monkeypatch) -> None:
    main = _load_main_module()
    main.settings.enable_agent_os = True
    main.settings.require_agent_os = True

    def fake_build_agent_os_app(base_app):
        raise RuntimeError("AgentOS failed to initialize")

    monkeypatch.setattr(main, "build_agent_os_app", fake_build_agent_os_app)

    try:
        main.create_app()
    except RuntimeError as exc:
        assert "AgentOS failed to initialize" in str(exc)
    else:
        raise AssertionError("create_app() should fail when AgentOS is required.")
