"""FastAPI entrypoint for the UZone backend."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent_os import build_agent_os_app
from app.api.routes import api_router
from app.core.config import settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    base_app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Backend API for the UZone zoning verification platform.",
    )
    base_app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    base_app.include_router(api_router)

    if not settings.enable_agent_os:
        return base_app

    try:
        return build_agent_os_app(base_app)
    except Exception:
        logger.exception("Failed to initialize optional AgentOS integration.")
        if settings.require_agent_os:
            raise
        return base_app


app = create_app()
