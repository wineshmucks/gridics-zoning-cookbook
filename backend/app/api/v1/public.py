"""Public tenant configuration routes."""

import json
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_optional_auth_context
from app.core.security import AuthContext
from app.core.config import settings
from app.db.models import AssistantMessageFeedback, TenantClient
from app.services.shared.embed_service import (
    build_embed_widget_payload,
    decode_embed_session_token,
    get_tenant_embed_settings,
    issue_embed_session_token,
    normalize_embed_origin,
    verify_embed_secret,
)
from app.services.shared.platform_settings_service import get_platform_assistant_settings_json
from app.services.shared.clerk_service import clerk_organization_exists
from app.services.shared.tenant_service import (
    get_effective_assistant_disclaimer_text,
    get_tenant_path_alias,
    get_tenant_market,
    get_tenant_logo_path,
    normalize_tenant_path_alias,
    resolve_tenant_public_config,
    tenant_public_config_to_dict,
)

router = APIRouter()


def _parse_json_form_field(value: object, fallback: object) -> object:
    if not isinstance(value, str) or not value.strip():
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


class EmbedSessionCreateRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=100)
    origin: str = Field(min_length=1, max_length=255)


class EmbedSessionCreateResponse(BaseModel):
    token: str
    expires_at: str
    client_id: str
    city_name: str
    department_name: str
    market: str | None = None
    logo_path: str | None = None
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
    market: str | None = None
    logo_path: str | None = None
    assistant_disclaimer_text: str
    widget_title: str
    launcher_label: str
    accent_color: str
    allowed_origins: list[str]
    origin: str | None = None
    expires_at: str


class AssistantMessageFeedbackUpsertRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=100)
    agent_id: str = Field(min_length=1, max_length=100)
    surface: str = Field(default="public-assistant", min_length=1, max_length=100)
    conversation_id: str = Field(min_length=1, max_length=255)
    message_id: str = Field(min_length=1, max_length=255)
    run_id: str | None = Field(default=None, max_length=255)
    feedback_value: Literal["up", "down"] | None = None
    message_excerpt: str | None = Field(default=None, max_length=4000)
    feedback_tags: list[str] = Field(default_factory=list, max_length=10)


class AssistantMessageFeedbackUpsertResponse(BaseModel):
    message_id: str
    conversation_id: str
    feedback_value: Literal["up", "down"] | None = None


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


@router.put("/assistant-feedback", response_model=AssistantMessageFeedbackUpsertResponse)
def upsert_assistant_feedback(
    payload: AssistantMessageFeedbackUpsertRequest,
    db: Session = Depends(get_db),
    auth: AuthContext | None = Depends(get_optional_auth_context),
) -> dict:
    tenant_client = db.scalar(select(TenantClient).where(TenantClient.client_id == payload.client_id.strip()))
    if tenant_client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    existing = db.scalar(
        select(AssistantMessageFeedback).where(
            AssistantMessageFeedback.tenant_client_id == tenant_client.id,
            AssistantMessageFeedback.conversation_id == payload.conversation_id.strip(),
            AssistantMessageFeedback.message_id == payload.message_id.strip(),
        )
    )

    if payload.feedback_value is None:
        if existing is not None:
            db.delete(existing)
            db.commit()
        return {
            "message_id": payload.message_id.strip(),
            "conversation_id": payload.conversation_id.strip(),
            "feedback_value": None,
        }

    clerk_user_id = auth.user_id if auth is not None and auth.provider == "clerk" else None
    message_excerpt = payload.message_excerpt.strip() if payload.message_excerpt else None
    feedback_tags = [item.strip() for item in payload.feedback_tags if isinstance(item, str) and item.strip()]
    metadata_json = {"feedback_tags": feedback_tags} if feedback_tags else None

    if existing is None:
        existing = AssistantMessageFeedback(
            tenant_client_id=tenant_client.id,
            clerk_user_id=clerk_user_id,
            agent_id=payload.agent_id.strip(),
            surface=payload.surface.strip(),
            conversation_id=payload.conversation_id.strip(),
            message_id=payload.message_id.strip(),
            run_id=payload.run_id.strip() if payload.run_id else None,
            feedback_value=payload.feedback_value,
            message_excerpt=message_excerpt,
            metadata_json=metadata_json,
        )
        db.add(existing)
    else:
        existing.clerk_user_id = clerk_user_id or existing.clerk_user_id
        existing.agent_id = payload.agent_id.strip()
        existing.surface = payload.surface.strip()
        existing.run_id = payload.run_id.strip() if payload.run_id else None
        existing.feedback_value = payload.feedback_value
        existing.message_excerpt = message_excerpt
        existing.metadata_json = metadata_json

    db.commit()
    return {
        "message_id": existing.message_id,
        "conversation_id": existing.conversation_id,
        "feedback_value": existing.feedback_value,
    }


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
                "logo_source": "jurisdiction" if get_tenant_logo_path(customer.settings_json) else None,
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
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

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
    assistant_disclaimer_text = get_effective_assistant_disclaimer_text(
        get_platform_assistant_settings_json(db),
        tenant_client.settings_json,
    )
    normalized_origin = normalize_embed_origin(payload.origin)
    if not normalized_origin:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid origin")

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
        market=get_tenant_market(tenant_client.settings_json),
    )
    response_payload = build_embed_widget_payload(
        tenant_client=tenant_client,
        embed_settings=embed_settings,
        token=token,
        expires_at=expires_at,
        assistant_disclaimer_text=assistant_disclaimer_text,
        embed_origin=normalized_origin,
    )
    response_payload["market"] = get_tenant_market(tenant_client.settings_json)
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
        market=str(payload.get("market") or "") if payload.get("market") else None,
        logo_path=str(payload.get("logo_path") or "") if payload.get("logo_path") else None,
        assistant_disclaimer_text=str(payload.get("assistant_disclaimer_text") or ""),
        widget_title=str(payload.get("widget_title") or f"Ask {payload.get('city_name') or 'UZone'}"),
        launcher_label=str(payload.get("launcher_label") or "Have a question?"),
        accent_color=str(payload.get("accent_color") or "#0b67c2"),
        allowed_origins=[str(payload.get("origin") or "")] if payload.get("origin") else [],
        origin=str(payload.get("origin") or "") if payload.get("origin") else None,
        expires_at=str(payload.get("exp") or ""),
    ).model_dump()
