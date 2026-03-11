"""Optional local Agno AgentOS integration for the UZone backend."""

from __future__ import annotations

from fastapi import FastAPI


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
        base_app=base_app,
        id="uzone-agent-os",
        name="UZone Agents",
        description="Agno runtime for UZone",
        telemetry=False,
        auto_provision_dbs=False,
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
