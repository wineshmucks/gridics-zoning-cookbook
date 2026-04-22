"""FastAPI entrypoint for the UZone backend."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent_os import build_agent_os_app
from app.api.routes import api_router
from app.core.config import settings

logger = logging.getLogger(__name__)

LOCAL_BRANDED_ORIGIN_REGEX = r"^http://([a-z0-9-]+\.)*gridics\.(local|test):3001$"


def create_app() -> FastAPI:
    base_app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Backend API for the Gridics UZone platform.",
    )
    base_app.state.agent_os_enabled = False

    @base_app.middleware("http")
    async def rewrite_agent_os_api_paths(request, call_next):
        path = request.scope.get("path", "")
        if path == "/api/config" or path.startswith("/api/config/"):
            rewritten = path[4:]
            request.scope["path"] = rewritten
            if request.scope.get("raw_path") is not None:
                request.scope["raw_path"] = rewritten.encode()
        elif path.startswith("/api/agents") or path.startswith("/api/teams"):
            rewritten = path[4:]
            request.scope["path"] = rewritten
            if request.scope.get("raw_path") is not None:
                request.scope["raw_path"] = rewritten.encode()

        return await call_next(request)

    base_app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()],
        allow_origin_regex=LOCAL_BRANDED_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    base_app.include_router(api_router)

    if not settings.enable_agent_os:
        return base_app

    try:
        app = build_agent_os_app(base_app)
        app.state.agent_os_enabled = True
        return app
    except Exception:
        logger.exception("Failed to initialize optional AgentOS integration.")
        if settings.require_agent_os:
            raise
        return base_app


app = create_app()
