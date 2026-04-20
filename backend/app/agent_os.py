"""Optional local Agno AgentOS integration for the UZone backend."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

from app.agents.storage import get_agno_db
from app.services.embed_service import decode_embed_session_token, parse_embed_token_from_header
from app.core.config import settings

PUBLIC_CUSTOMER_ZONING_ASSISTANT_ROUTE_IDS = (
    "customer_zoning_team",
    "customer-zoning-team",
    "customer-zoning-agent",
)
CUSTOMER_ZONING_TEAM_ROUTE_PREFIX = "/teams/customer_zoning_team"

logger = logging.getLogger(__name__)


def _rewrite_scope_path(request, prefix: str) -> None:
    original_path = request.scope["path"]
    rewritten = request.scope["path"].replace(prefix, CUSTOMER_ZONING_TEAM_ROUTE_PREFIX, 1)
    request.scope["path"] = rewritten
    if request.scope.get("raw_path") is not None:
        request.scope["raw_path"] = rewritten.encode()
    logger.debug("Rewrote AgentOS path %s -> %s", original_path, rewritten)


def _rewrite_customer_zoning_assistant_route(request) -> bool:
    path = request.scope.get("path", "")
    for route_id in PUBLIC_CUSTOMER_ZONING_ASSISTANT_ROUTE_IDS:
        for prefix in (f"/api/agents/{route_id}", f"/agents/{route_id}"):
            if path.startswith(prefix):
                _rewrite_scope_path(request, prefix)
                return True
    return False


def _build_agent_os_db():
    return get_agno_db()


def build_agent_os_app(base_app: FastAPI) -> FastAPI:
    from agno.os import AgentOS
    from app.agents import registry as agent_registry

    all_agents = getattr(agent_registry, "ALL_AGENTS", [])
    all_teams = getattr(agent_registry, "ALL_TEAMS", [])
    
    agent_os = AgentOS(
        agents=all_agents,
        teams=all_teams,
        db=_build_agent_os_db(),
        base_app=base_app,
        id="uzone-agent-os",
        name="UZone Agents",
        description="Agno runtime for UZone",
        tracing=True,
        auto_provision_dbs=True,
    )
    app = agent_os.get_app()

    @app.middleware("http")
    async def log_agent_os_requests(request, call_next):
        path = request.scope.get("path", "")
        debug_enabled = request.query_params.get("debug") == "1" or request.headers.get("x-uzone-debug") == "1"
        is_agent_path = path.startswith("/agents/") or path.startswith("/api/agents/")
        started_at = time.perf_counter() if is_agent_path else None
        if is_agent_path:
            logger.debug(
                "AgentOS request start method=%s path=%s query=%s debug=%s client=%s agent_os=%s",
                request.method,
                path,
                request.scope.get("query_string", b"").decode(errors="ignore"),
                debug_enabled,
                request.client.host if request.client else None,
                request.headers.get("x-uzone-clientid"),
            )
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.exception(
                "AgentOS request failed method=%s path=%s query=%s debug=%s",
                request.method,
                path,
                request.scope.get("query_string", b"").decode(errors="ignore"),
                debug_enabled,
            )
            if is_agent_path and debug_enabled:
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "detail": str(exc),
                        "error_type": exc.__class__.__name__,
                        "path": path,
                    },
                )
            if is_agent_path:
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "Assistant request failed."},
                )
            raise

        if is_agent_path and started_at is not None:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            logger.debug(
                "AgentOS request complete method=%s path=%s status=%s elapsed_ms=%.1f debug=%s",
                request.method,
                path,
                response.status_code,
                elapsed_ms,
                debug_enabled,
            )
        return response

    @app.middleware("http")
    async def rewrite_agent_os_api_paths(request, call_next):
        path = request.scope.get("path", "")
        embed_token = request.headers.get("x-uzone-embed-token")
        if embed_token and (path.startswith("/agents/") or path.startswith("/api/agents/")):
            token = parse_embed_token_from_header(f"Bearer {embed_token}")
            claims = decode_embed_session_token(token)
            request.state.embed_session = claims
            logger.debug("AgentOS request path=%s embed_session_client=%s", path, claims.get("client_id"))

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
            logger.debug("Rewrote generic AgentOS API path %s -> %s", path, rewritten)

        return await call_next(request)

    return app
