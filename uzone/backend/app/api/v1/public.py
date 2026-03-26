"""Public tenant configuration routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import settings
from app.db.models import TenantClient
from app.services.clerk_service import get_clerk_organization
from app.services.tenant_service import (
    get_tenant_path_alias,
    normalize_tenant_path_alias,
    resolve_tenant_public_config,
    tenant_public_config_to_dict,
)

router = APIRouter()


def _ensure_tenant_client_for_organization(db: Session, organization_id: str | None) -> TenantClient | None:
    normalized_org_id = organization_id.strip() if organization_id else ""
    if not normalized_org_id:
        return None

    existing = db.scalar(
        select(TenantClient).where(TenantClient.clerk_organization_id == normalized_org_id)
    )
    if existing is not None:
        return existing

    organization = get_clerk_organization(normalized_org_id)
    if not organization:
        return None

    organization_name = str(organization.get("name") or "").strip() or normalized_org_id
    tenant_client = TenantClient(
        client_id=normalized_org_id,
        clerk_organization_id=normalized_org_id,
        city_name=organization_name,
        department_name=f"{organization_name} Planning & Zoning Department",
        is_active=True,
    )
    db.add(tenant_client)
    db.commit()
    db.refresh(tenant_client)
    return tenant_client


@router.get("/client-config")
def get_client_config(
    request: Request,
    clientid: str | None = Query(default=None),
    orgid: str | None = Query(default=None),
    path_alias: str | None = Query(default=None),
    host: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    resolved = resolve_tenant_public_config(
        db,
        client_id=clientid,
        organization_id=orgid,
        path_alias=path_alias,
        host=host or request.headers.get("host"),
    )
    if resolved is None and orgid:
        tenant_client = _ensure_tenant_client_for_organization(db, orgid)
        if tenant_client is not None:
            resolved = resolve_tenant_public_config(
                db,
                client_id=clientid,
                organization_id=orgid,
                path_alias=path_alias,
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
        customer_client_id = customer.client_id.strip() if customer.client_id else None
        customer_org_id = customer.clerk_organization_id.strip() if customer.clerk_organization_id else None
        customer_org_id_lower = customer_org_id.lower() if customer_org_id else None
        customer_client_id_lower = customer_client_id.lower() if customer_client_id else None
        public_org_id = customer_org_id or customer_client_id

        if customer_client_id_lower == "gridics":
            continue
        if not public_org_id:
            continue
        if settings.clerk_secret_key and customer_org_id and get_clerk_organization(customer_org_id) is None:
            continue
        if gridics_org_id and customer_org_id_lower == gridics_org_id:
            continue

        results.append(
            {
                "orgid": public_org_id,
                "path_alias": get_tenant_path_alias(customer.settings_json),
                "client_id": customer.client_id,
                "city_name": customer.city_name,
                "department_name": customer.department_name,
            }
        )

    return results


@router.get("/path-alias")
def resolve_path_alias(
    path: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> dict:
    try:
        normalized_path = normalize_tenant_path_alias(path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    resolved = resolve_tenant_public_config(db, path_alias=normalized_path)
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Path alias not found")

    return {
        "path_alias": resolved.path_alias or normalized_path,
        "orgid": resolved.clerk_organization_id or resolved.client_id,
        "client_id": resolved.client_id,
    }
