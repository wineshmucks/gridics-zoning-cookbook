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
    return agent_os.get_app()
