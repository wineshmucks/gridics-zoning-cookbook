"""Optional local Agno AgentOS integration for the UZone backend."""

from __future__ import annotations

from fastapi import FastAPI

from app.core.config import settings


def _build_agent_os_db():
    from agno.db.postgres.postgres import PostgresDb

    # Store AgentOS runs in the app database so completed-run lookups work
    # consistently across ECS task restarts and between requests.
    return PostgresDb(
        db_url=settings.database_url,
        db_schema="agent_os",
        session_table="agent_os_sessions",
        memory_table="agent_os_memories",
        metrics_table="agent_os_metrics",
        eval_table="agent_os_eval_runs",
        traces_table="agent_os_traces",
        spans_table="agent_os_spans",
        versions_table="agent_os_schema_versions",
        components_table="agent_os_components",
        component_configs_table="agent_os_component_configs",
        component_links_table="agent_os_component_links",
        learnings_table="agent_os_learnings",
        schedules_table="agent_os_schedules",
        schedule_runs_table="agent_os_schedule_runs",
        approvals_table="agent_os_approvals",
    )


def build_agent_os_app(base_app: FastAPI) -> FastAPI:
    try:
        from agno.os import AgentOS
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Agno AgentOS support is not installed in the backend environment. "
            "Rebuild the backend image so the current Python dependencies are installed."
        ) from exc

    from app.agents.registry import ALL_AGENTS

    agent_os = AgentOS(
        agents=ALL_AGENTS,
        db=_build_agent_os_db(),
        base_app=base_app,
        id="uzone-agent-os",
        name="UZone Agents",
        description="Agno runtime for UZone",
        telemetry=False,
        auto_provision_dbs=True,
    )
    app = agent_os.get_app()

    @app.middleware("http")
    async def rewrite_agent_os_api_paths(request, call_next):
        path = request.scope.get("path", "")
        if path == "/api/config" or path.startswith("/api/config/"):
            rewritten = path[4:]
            request.scope["path"] = rewritten
            if request.scope.get("raw_path") is not None:
                request.scope["raw_path"] = rewritten.encode()
        elif path.startswith("/api/agents"):
            rewritten = path[4:]
            request.scope["path"] = rewritten
            if request.scope.get("raw_path") is not None:
                request.scope["raw_path"] = rewritten.encode()

        return await call_next(request)

    return app
