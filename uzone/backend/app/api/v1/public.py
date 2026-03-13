"""Public tenant configuration routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import settings
from app.db.models import TenantClient
from app.services.clerk_service import clerk_organization_exists
from app.services.tenant_service import resolve_tenant_public_config, tenant_public_config_to_dict

router = APIRouter()


@router.get("/client-config")
def get_client_config(
    request: Request,
    clientid: str | None = Query(default=None),
    orgid: str | None = Query(default=None),
    host: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    resolved = resolve_tenant_public_config(
        db,
        client_id=clientid,
        organization_id=orgid,
        host=host or request.headers.get("host"),
    )
    if resolved is None:
        raise HTTPException(status_code=404, detail="Client configuration not found")
    return tenant_public_config_to_dict(resolved)


@router.get("/customers")
def list_public_customers(db: Session = Depends(get_db)) -> list[dict]:
    gridics_org_id = (
        settings.gridics_clerk_organization_id.strip().lower() if settings.gridics_clerk_organization_id else None
    )
    customers = db.scalars(
        select(TenantClient)
        .where(
            TenantClient.is_active.is_(True),
            TenantClient.clerk_organization_id.is_not(None),
        )
        .order_by(TenantClient.city_name.asc(), TenantClient.created_at.asc())
    ).all()

    results: list[dict] = []
    for customer in customers:
        customer_org_id = customer.clerk_organization_id.strip() if customer.clerk_organization_id else None
        customer_org_id_lower = customer_org_id.lower() if customer_org_id else None
        if customer.client_id.strip().lower() == "gridics":
            continue
        if not customer_org_id:
            continue
        if gridics_org_id and customer_org_id_lower == gridics_org_id:
            continue
        if not clerk_organization_exists(customer_org_id):
            continue

        results.append(
            {
                "orgid": customer_org_id,
                "client_id": customer.client_id,
                "city_name": customer.city_name,
                "department_name": customer.department_name,
            }
        )

    return results
