"""Optional local Agno AgentOS integration for the UZone backend."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

from app.agents.storage import get_agno_db
from app.services.shared.embed_service import decode_embed_session_token, parse_embed_token_from_header
from app.core.config import settings

CUSTOMER_ZONING_ASSISTANT_TARGET_ID = "customer_zoning_team"
LEGACY_CUSTOMER_ZONING_ASSISTANT_TARGET_ID = "customer-zoning-agent"
PUBLIC_CUSTOMER_ZONING_ASSISTANT_TARGET_ID = "customer-zoning-team"

CUSTOMER_ZONING_ASSISTANT_ROUTE_IDS = (
    CUSTOMER_ZONING_ASSISTANT_TARGET_ID,
    PUBLIC_CUSTOMER_ZONING_ASSISTANT_TARGET_ID,
    LEGACY_CUSTOMER_ZONING_ASSISTANT_TARGET_ID,
)

CUSTOMER_ZONING_AGENT_ROUTE_PREFIX = "/agents/customer-zoning-agent"

logger = logging.getLogger(__name__)


def _emit_agentos_console_log(message: str) -> None:
    logger.warning(message)
    print(message, flush=True)


def _rewrite_scope_path(request, prefix: str) -> None:
    original_path = request.scope["path"]
    rewritten = request.scope["path"].replace(prefix, CUSTOMER_ZONING_AGENT_ROUTE_PREFIX, 1)
    request.scope["path"] = rewritten
    if request.scope.get("raw_path") is not None:
        request.scope["raw_path"] = rewritten.encode()
    logger.debug("Rewrote AgentOS path %s -> %s", original_path, rewritten)


def _rewrite_customer_zoning_assistant_route(request) -> bool:
    path = request.scope.get("path", "")
    for route_id in CUSTOMER_ZONING_ASSISTANT_ROUTE_IDS:
        for prefix in (f"/api/agents/{route_id}", f"/agents/{route_id}"):
            if path.startswith(prefix):
                _rewrite_scope_path(request, prefix)
                return True
    return False


def _build_agent_os_db():
    return get_agno_db()


def _build_customer_zoning_agent():
    from app.agents.zoning_agent import build_customer_zoning_agent

    return build_customer_zoning_agent()


def build_agent_os_app(base_app: FastAPI) -> FastAPI:
    from agno.os import AgentOS

    agent_os = AgentOS(
        agents=[_build_customer_zoning_agent()],
        teams=[],
        db=_build_agent_os_db(),
        base_app=base_app,
        id="gridics-agent-os",
        name="Gridics Agents",
        description="Gridics Agents",
        tracing=True,
        auto_provision_dbs=True,
    )
    app = agent_os.get_app()

    @app.middleware("http")
    async def log_agent_os_requests(request, call_next):
        path = request.scope.get("path", "")
        debug_enabled = request.query_params.get("debug") == "1" or request.headers.get("x-uzone-debug") == "1"
        is_agent_path = path.startswith("/agents/") or path.startswith("/api/agents/")
        is_team_path = path.startswith("/teams/") or path.startswith("/api/teams/")
        started_at = time.perf_counter() if is_agent_path else None
        if is_agent_path or is_team_path:
            route_parts = [part for part in path.split("/") if part]
            route_kind = route_parts[0] if route_parts else None
            route_target = route_parts[1] if len(route_parts) > 1 else None
            logger.debug(
                "AgentOS request start method=%s path=%s route_kind=%s route_target=%s query=%s debug=%s client=%s agent_os=%s",
                request.method,
                path,
                route_kind,
                route_target,
                request.scope.get("query_string", b"").decode(errors="ignore"),
                debug_enabled,
                request.client.host if request.client else None,
                request.headers.get("x-uzone-clientid"),
            )
            _emit_agentos_console_log(
                f"[AgentOS] request routed to {route_kind}={route_target} path={path}"
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
        elif path.startswith("/api/agents") or path.startswith("/api/teams"):
            rewritten = path[4:]
            request.scope["path"] = rewritten
            if request.scope.get("raw_path") is not None:
                request.scope["raw_path"] = rewritten.encode()
            logger.debug("Rewrote generic AgentOS API path %s -> %s", path, rewritten)

        return await call_next(request)

    return app
