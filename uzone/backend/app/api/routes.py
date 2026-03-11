"""Top-level API router composition."""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.dev import router as dev_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.payments import router as payments_router
from app.api.v1.properties import router as properties_router
from app.api.v1.public import router as public_router
from app.api.v1.reports import router as reports_router
from app.api.v1.requests import router as requests_router
from app.api.v1.staff_requests import router as staff_requests_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(dev_router, prefix="/api/dev", tags=["dev"])
api_router.include_router(documents_router, prefix="/api/documents", tags=["documents"])
api_router.include_router(auth_router, prefix="/api/auth", tags=["auth"])
api_router.include_router(payments_router, prefix="/api/payments", tags=["payments"])
api_router.include_router(public_router, prefix="/api/public", tags=["public"])
api_router.include_router(properties_router, prefix="/api/properties", tags=["properties"])
api_router.include_router(requests_router, prefix="/api/requests", tags=["requests"])
api_router.include_router(staff_requests_router, prefix="/api/staff/requests", tags=["staff-requests"])
api_router.include_router(admin_router, prefix="/api/admin", tags=["admin"])
api_router.include_router(reports_router, prefix="/api/reports", tags=["reports"])
