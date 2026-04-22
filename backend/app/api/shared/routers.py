"""Routers for shared API endpoints."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.dev import router as dev_router
from app.api.v1.gridics import router as gridics_router
from app.api.v1.health import router as health_router
from app.api.v1.properties import router as properties_router
from app.api.v1.public import router as public_router

router = APIRouter(tags=["shared"])
router.include_router(health_router)
router.include_router(dev_router, prefix="/api/dev", tags=["dev"])
router.include_router(gridics_router, prefix="/api/gridics", tags=["gridics"])
router.include_router(auth_router, prefix="/api/auth", tags=["auth"])
router.include_router(public_router, prefix="/api/public", tags=["public"])
router.include_router(properties_router, prefix="/api/properties", tags=["properties"])
