"""Optional local Agno AgentOS integration for the UZone backend."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi import HTTPException, status

from app.services.embed_service import decode_embed_session_token, parse_embed_token_from_header

from app.core.config import settings

PUBLIC_CUSTOMER_ZONING_ASSISTANT_ROUTE_IDS = (
    "customer-zoning-team",
    "customer-zoning-agent",
)
CUSTOMER_ZONING_TEAM_ROUTE_PREFIX = "/teams/customer_zoning_team"


def _rewrite_scope_path(request, prefix: str) -> None:
    rewritten = request.scope["path"].replace(prefix, CUSTOMER_ZONING_TEAM_ROUTE_PREFIX, 1)
    request.scope["path"] = rewritten
    if request.scope.get("raw_path") is not None:
        request.scope["raw_path"] = rewritten.encode()


def _rewrite_customer_zoning_assistant_route(request) -> bool:
    path = request.scope.get("path", "")
    for route_id in PUBLIC_CUSTOMER_ZONING_ASSISTANT_ROUTE_IDS:
        for prefix in (f"/api/agents/{route_id}", f"/agents/{route_id}"):
            if path.startswith(prefix):
                _rewrite_scope_path(request, prefix)
                return True
    return False


def _build_agent_os_db():
    from agno.db.postgres.postgres import PostgresDb

    # Store AgentOS runs in the app database so completed-run lookups work
    # consistently across ECS task restarts and between requests.
    return PostgresDb(
        db_url=settings.database_url,
        db_schema="agent_os",
        session_table="aos_sessions",
        memory_table="aos_memories",
        metrics_table="aos_metrics",
        eval_table="aos_eval_runs",
        traces_table="aos_traces",
        spans_table="aos_spans",
        versions_table="aos_schema_versions",
        components_table="aos_components",
        component_configs_table="aos_component_configs",
        component_links_table="aos_component_links",
        learnings_table="aos_learnings",
        schedules_table="aos_schedules",
        schedule_runs_table="aos_schedule_runs",
        approvals_table="aos_approvals",
    )


def build_agent_os_app(base_app: FastAPI) -> FastAPI:
    try:
        from agno.os import AgentOS
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Agno AgentOS support is not installed in the backend environment. "
            "Rebuild the backend image so the current Python dependencies are installed."
        ) from exc

    try:
        from app.agents.registry import ALL_AGENTS
    except ImportError:
        ALL_AGENTS = []

    try:
        from app.agents.registry import ALL_TEAMS
    except ImportError:
        ALL_TEAMS = []

    agent_os = AgentOS(
        agents=ALL_AGENTS,
        teams=ALL_TEAMS,
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
        embed_token = request.headers.get("x-uzone-embed-token")
        if embed_token and (path.startswith("/agents/") or path.startswith("/api/agents/")):
            token = parse_embed_token_from_header(f"Bearer {embed_token}")
            claims = decode_embed_session_token(token)
            request.state.embed_session = claims

        if path == "/api/config" or path.startswith("/api/config/"):
            rewritten = path[4:]
            request.scope["path"] = rewritten
            if request.scope.get("raw_path") is not None:
                request.scope["raw_path"] = rewritten.encode()
        elif _rewrite_customer_zoning_assistant_route(request):
            pass
        elif path.startswith("/api/agents"):
            rewritten = path[4:]
            request.scope["path"] = rewritten
            if request.scope.get("raw_path") is not None:
                request.scope["raw_path"] = rewritten.encode()

        return await call_next(request)

    return app
