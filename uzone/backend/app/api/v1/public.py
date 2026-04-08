"""Public tenant configuration routes."""

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import settings
from app.db.models import TenantClient
from app.services.embed_service import (
    build_embed_widget_payload,
    decode_embed_session_token,
    get_tenant_embed_settings,
    issue_embed_session_token,
    normalize_embed_origin,
    verify_embed_secret,
)
from app.services.clerk_service import clerk_organization_exists
from app.services.tenant_service import (
    get_tenant_path_alias,
    get_tenant_logo_path,
    get_tenant_assistant_disclaimer_text,
    normalize_tenant_path_alias,
    resolve_tenant_public_config,
    tenant_public_config_to_dict,
)

router = APIRouter()


class EmbedSessionCreateRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=100)
    origin: str = Field(min_length=1, max_length=255)


class EmbedSessionCreateResponse(BaseModel):
    token: str
    expires_at: str
    client_id: str
    city_name: str
    department_name: str
    assistant_disclaimer_text: str
    widget_title: str
    launcher_label: str
    accent_color: str
    allowed_origins: list[str]
    origin: str | None = None


class EmbedSessionReadResponse(BaseModel):
    client_id: str
    city_name: str
    department_name: str
    assistant_disclaimer_text: str
    widget_title: str
    launcher_label: str
    accent_color: str
    allowed_origins: list[str]
    origin: str | None = None
    expires_at: str


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
    normalized_path_alias = path_alias.strip() if isinstance(path_alias, str) and path_alias.strip() else None
    resolved = resolve_tenant_public_config(
        db,
        client_id=clientid,
        organization_id=orgid,
        path_alias=normalized_path_alias,
        host=host or request.headers.get("host"),
    )
    if resolved is None and orgid:
        tenant_client = _ensure_tenant_client_for_organization(db, orgid)
        if tenant_client is not None:
            resolved = resolve_tenant_public_config(
                db,
                client_id=clientid,
                organization_id=orgid,
                path_alias=normalized_path_alias,
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
        if customer_org_id and not clerk_organization_exists(customer_org_id):
            continue
        if gridics_org_id and customer_org_id_lower == gridics_org_id:
            continue

        results.append(
            {
                "orgid": public_org_id,
                "client_id": customer.client_id,
                "path_alias": get_tenant_path_alias(customer.settings_json),
                "logo_path": get_tenant_logo_path(customer.settings_json),
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


@router.post("/embed/sessions", response_model=EmbedSessionCreateResponse)
def create_embed_session(
    payload: EmbedSessionCreateRequest,
    db: Session = Depends(get_db),
    embed_secret: str | None = Header(default=None, alias="X-UZone-Embed-Secret"),
) -> dict:
    tenant_client = db.scalar(select(TenantClient).where(TenantClient.client_id == payload.client_id.strip()))
    if tenant_client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    embed_settings = get_tenant_embed_settings(tenant_client.settings_json)
    assistant_disclaimer_text = get_tenant_assistant_disclaimer_text(tenant_client.settings_json)
    normalized_origin = normalize_embed_origin(payload.origin)
    if not normalized_origin:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid origin")

    if not embed_settings.is_active or not embed_settings.secret_hash:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Embed integration is not configured for this tenant",
        )

    provided_secret = embed_secret or ""
    if not verify_embed_secret(provided_secret, embed_settings.secret_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid embed secret")

    if embed_settings.allowed_origins and normalized_origin not in embed_settings.allowed_origins:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin is not allowed")

    token, expires_at = issue_embed_session_token(
        tenant_client=tenant_client,
        embed_origin=normalized_origin,
        assistant_disclaimer_text=assistant_disclaimer_text,
        widget_title=embed_settings.widget_title,
        launcher_label=embed_settings.launcher_label,
        accent_color=embed_settings.accent_color,
    )
    response_payload = build_embed_widget_payload(
        tenant_client=tenant_client,
        embed_settings=embed_settings,
        token=token,
        expires_at=expires_at,
        assistant_disclaimer_text=assistant_disclaimer_text,
        embed_origin=normalized_origin,
    )
    return EmbedSessionCreateResponse(**response_payload).model_dump()


@router.get("/embed/session", response_model=EmbedSessionReadResponse)
def read_embed_session(request: Request) -> dict:
    token = request.headers.get("x-uzone-embed-token") or ""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing embed session token")

    payload = decode_embed_session_token(token)
    return EmbedSessionReadResponse(
        client_id=str(payload.get("client_id") or ""),
        city_name=str(payload.get("city_name") or ""),
        department_name=str(payload.get("department_name") or ""),
        assistant_disclaimer_text=str(payload.get("assistant_disclaimer_text") or ""),
        widget_title=str(payload.get("widget_title") or f"Ask {payload.get('city_name') or 'UZone'}"),
        launcher_label=str(payload.get("launcher_label") or "Have a question?"),
        accent_color=str(payload.get("accent_color") or "#0b67c2"),
        allowed_origins=[str(payload.get("origin") or "")] if payload.get("origin") else [],
        origin=str(payload.get("origin") or "") if payload.get("origin") else None,
        expires_at=str(payload.get("exp") or ""),
    ).model_dump()
