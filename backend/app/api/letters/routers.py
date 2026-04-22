"""Routers for letter workflow API endpoints."""

from fastapi import APIRouter

from app.api.v1.documents import router as documents_router
from app.api.v1.payments import router as payments_router
from app.api.v1.reports import router as reports_router
from app.api.v1.requests import router as requests_router
from app.api.v1.staff_requests import router as staff_requests_router

router = APIRouter(tags=["letters"])
router.include_router(documents_router, prefix="/api/documents", tags=["documents"])
router.include_router(requests_router, prefix="/api/requests", tags=["requests"])
router.include_router(staff_requests_router, prefix="/api/staff/requests", tags=["staff-requests"])
router.include_router(payments_router, prefix="/api/payments", tags=["payments"])
router.include_router(reports_router, prefix="/api/reports", tags=["reports"])
