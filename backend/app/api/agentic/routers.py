"""Routers for agentic API endpoints."""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router

router = APIRouter(tags=["agentic"])
router.include_router(admin_router, prefix="/api/admin", tags=["admin"])
