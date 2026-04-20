"""Health and route inspection endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.config import settings

router = APIRouter()


@router.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/health")
def root_health() -> dict:
    return {"status": "ok"}


@router.get("/api/health/agent-os")
@router.get("/health/agent-os")
def agent_os_health(request: Request):
    agent_os_enabled = bool(getattr(request.app.state, "agent_os_enabled", False))
    status_code = 200 if agent_os_enabled else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if agent_os_enabled else "unavailable",
            "agent_os_enabled": agent_os_enabled,
            "require_agent_os": settings.require_agent_os,
        },
    )


@router.get("/routes")
def routes() -> dict:
    route_map = {
        "health": [
            "GET /api/health",
            "GET /health",
            "GET /api/health/agent-os",
            "GET /health/agent-os",
            "GET /routes",
        ],
        "auth": [
            "POST /api/auth/register",
            "POST /api/auth/login",
            "GET /api/auth/me",
        ],
        "documents": [
            "GET /api/documents/{version_id}/download",
        ],
        "dev": [
            "GET /api/dev/identities",
        ],
        "payments": [
            "POST /api/payments/webhook/stripe",
        ],
        "properties": [
            "POST /api/properties",
            "GET /api/properties/search",
            "GET /api/properties/{property_id}",
            "POST /api/properties/{property_id}/snapshots",
        ],
        "requests": [
            "POST /api/requests",
            "GET /api/requests",
            "GET /api/requests/{request_id}",
            "GET /api/requests/{request_id}/status-events",
            "POST /api/requests/{request_id}/submit",
            "POST /api/requests/{request_id}/quote",
            "GET /api/requests/{request_id}/quote",
            "POST /api/requests/{request_id}/checkout",
            "POST /api/requests/{request_id}/payment-received",
        ],
        "staff_requests": [
            "GET /api/staff/requests",
            "GET /api/staff/requests/{request_id}",
            "GET /api/staff/requests/{request_id}/status-events",
            "POST /api/staff/requests/{request_id}/assign",
            "POST /api/staff/requests/{request_id}/start-review",
            "GET /api/staff/requests/{request_id}/notes",
            "POST /api/staff/requests/{request_id}/notes",
            "POST /api/staff/requests/{request_id}/drafts",
            "POST /api/staff/requests/{request_id}/approve",
            "POST /api/staff/requests/{request_id}/deliver",
        ],
        "admin": [
            "GET /api/admin/jurisdictions",
            "POST /api/admin/jurisdictions",
            "GET /api/admin/fees",
            "POST /api/admin/fees/schedules",
            "POST /api/admin/fees/items",
            "GET /api/admin/letter-templates",
            "POST /api/admin/letter-templates",
            "GET /api/admin/clients/{organization_id}/zoning-knowledge",
            "POST /api/admin/clients/{organization_id}/zoning-knowledge/ingest",
            "POST /api/admin/clients/{organization_id}/zoning-knowledge/query",
        ],
        "reports": [
            "GET /api/reports/summary",
        ],
    }
    if settings.enable_agent_os:
        route_map["agent_os"] = [
            "GET /config",
            "GET /agents",
            "POST /agents/{agent_id}/runs",
            "GET /agents/{agent_id}/runs/{run_id}",
            "GET /api/gridics/markets",
            "GET /api/gridics/property-record",
            "GET /api/gridics/search",
            "POST /api/instant-feasibility",
        ]
    return route_map
