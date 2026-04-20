"""Admin routes."""

import logging
import re
from mimetypes import guess_type
from pathlib import Path
from secrets import token_hex
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.agents.assistant_defaults import CODE_DEFAULT_ASSISTANT_MODEL_TARGETS
from app.db.models import (
    EmailTemplate,
    FeeSchedule,
    FeeScheduleItem,
    Jurisdiction,
    JurisdictionHomePageContent,
    LetterTemplate,
    TenantClient,
    TenantDomain,
    User,
    ZoningCodeDocument,
    ZoningCodeIngestionRun,
    ZoningCodeSection,
)
from app.schemas import (
    EmailTemplateClientContextRead,
    EmailTemplateEffectiveRead,
    EmailTemplateOverrideUpsert,
    EmailTemplatesResponse,
    FeeScheduleCreate,
    FeeScheduleItemCreate,
    FeeScheduleItemRead,
    FeeScheduleRead,
    FeeStructureClientContextRead,
    FeeStructureResponse,
    FeeStructureUpsert,
    HomePageClientContextRead,
    HomePageContentResponse,
    HomePageContentUpsert,
    JurisdictionCreate,
    JurisdictionRead,
    DatabaseCleanupResultRead,
    DatabaseInfoRead,
    LetterTemplateCreate,
    LetterTemplateRead,
    PlatformAssistantSettingsRead,
    PlatformAssistantSettingsUpdate,
    TenantClientCreate,
    TenantExperienceSettingsRead,
    TenantExperienceSettingsUpdate,
    TenantClientRead,
    TenantClientUpdate,
    ZoningKnowledgeIngestRequest,
    ZoningKnowledgeQueryRequest,
    ZoningKnowledgeQueryResponse,
    ZoningKnowledgeStatusRead,
)
from app.core.config import settings
from app.services.assistant_conversation_review_service import list_assistant_conversation_reviews
from app.services.database_maintenance_service import cleanup_dangling_records, get_database_info
from app.services.email_template_service import get_default_email_templates, get_effective_email_templates
from app.services.cache_service import get_cache_service
from app.services.clerk_service import get_clerk_organization
from app.services.embed_service import (
    build_embed_widget_payload,
    generate_embed_secret,
    get_tenant_embed_settings,
    issue_embed_session_token,
    hash_embed_secret,
    merge_tenant_embed_settings,
)
from app.services.logo_storage import (
    delete_asset,
    delete_asset_namespace,
    download_asset,
    is_asset_storage_enabled,
    upload_asset,
)
from app.services.assistant_telemetry_service import list_assistant_run_telemetry
from app.services.fee_service import ensure_active_fee_schedule_for_tenant, update_fee_structure_for_tenant
from app.services.clerk_service import delete_clerk_organization, update_clerk_organization
from app.services.platform_settings_service import get_platform_assistant_settings_json, set_platform_assistant_settings_json
from app.services.tenant_service import (
    DEFAULT_ASSISTANT_DISCLAIMER_TEXT,
    get_effective_assistant_disclaimer_text,
    get_tenant_path_alias,
    get_home_page_content_record,
    get_home_page_content_payload,
    get_tenant_assistant_agent_prompts,
    get_tenant_assistant_settings,
    get_tenant_assistant_disclaimer_text,
    get_tenant_experience_settings,
    get_tenant_logo_path,
    has_home_page_content_storage,
    invalidate_tenant_cache,
    merge_tenant_branding_settings,
    merge_tenant_market_settings,
    merge_tenant_path_alias_settings,
    merge_tenant_experience_settings,
    normalize_tenant_path_alias,
)
from app.services.zoning_knowledge_service import (
    build_zoning_knowledge_status,
    run_zoning_code_ingestion,
    start_zoning_code_ingestion,
    query_customer_zoning_knowledge,
)

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_LOGO_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}
LOGO_FILE_EXTENSION_BY_CONTENT_TYPE = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}
MAX_LOGO_UPLOAD_BYTES = 2 * 1024 * 1024


class TenantEmbedSettingsRead(BaseModel):
    is_active: bool
    allowed_origins: list[str] = Field(default_factory=list)
    widget_title: str | None = None
    launcher_label: str | None = None
    accent_color: str | None = None
    has_secret: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class TenantEmbedSettingsUpdate(BaseModel):
    allowed_origins: list[str] = Field(default_factory=list)
    widget_title: str | None = Field(default=None, max_length=255)
    launcher_label: str | None = Field(default=None, max_length=255)
    accent_color: str | None = Field(default=None, max_length=50)
    is_active: bool = True


class TenantEmbedSettingsCreateResponse(TenantEmbedSettingsRead):
    secret: str


class TenantEmbedPreviewSecretResponse(BaseModel):
    secret: str


class TenantEmbedPreviewSessionRequest(BaseModel):
    origin: str = Field(min_length=1, max_length=255)


class TenantEmbedPreviewSessionResponse(BaseModel):
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


class AssistantTelemetryRunRead(BaseModel):
    id: str
    run_scope: str
    agent_id: str | None = None
    conversation_id: str | None = None
    message_id: str | None = None
    run_id: str | None = None
    session_id: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
    model_id: str | None = None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float | None = None
    time_to_first_token: float | None = None
    duration_seconds: float | None = None
    created_at: str
    metrics_json: dict | None = None


class AssistantTelemetrySummaryRead(BaseModel):
    total_runs: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float


class AssistantTelemetryResponse(BaseModel):
    summary: AssistantTelemetrySummaryRead
    runs: list[AssistantTelemetryRunRead]
    pagination: dict[str, int | bool | str | None]


class AssistantConversationReviewTurnRead(BaseModel):
    id: str
    created_at: str
    message_id: str | None = None
    run_id: str | None = None
    agent_id: str | None = None
    intent_type: str | None = None
    jurisdiction_status: str | None = None
    policy_decision: str | None = None
    reason_code: str | None = None
    payload_json: dict | list | str | int | float | bool | None = None


class AssistantConversationReviewRunRead(AssistantTelemetryRunRead):
    pass


class AssistantConversationReviewFeedbackRead(BaseModel):
    id: str
    clerk_user_id: str | None = None
    agent_id: str
    surface: str
    conversation_id: str
    message_id: str
    run_id: str | None = None
    feedback_value: str
    message_excerpt: str | None = None
    metadata_json: dict | None = None
    created_at: str


class AssistantConversationReviewRead(BaseModel):
    conversation_id: str
    latest_at: str | None = None
    turn_count: int
    run_count: int
    feedback_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float
    turns: list[AssistantConversationReviewTurnRead]
    runs: list[AssistantConversationReviewRunRead]
    feedback: list[AssistantConversationReviewFeedbackRead]


class AssistantConversationReviewSummaryRead(BaseModel):
    total_conversations: int
    total_turns: int
    total_runs: int
    total_feedback: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float


class AssistantConversationReviewResponse(BaseModel):
    summary: AssistantConversationReviewSummaryRead
    conversations: list[AssistantConversationReviewRead]
    pagination: dict[str, int | bool | str | None]


def _admin_fee_structure_cache_key(tenant_client: TenantClient) -> str:
    return f"admin:fee-structure:{tenant_client.id}"


def _admin_home_page_cache_key(tenant_client: TenantClient) -> str:
    return f"admin:home-page-content:{tenant_client.id}"


def _normalize_jurisdiction_code(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized[:100] or "jurisdiction"


def _ensure_tenant_jurisdiction(db: Session, tenant_client: TenantClient) -> Jurisdiction:
    if tenant_client.jurisdiction_id:
        jurisdiction = db.get(Jurisdiction, tenant_client.jurisdiction_id)
        if jurisdiction is not None:
            return jurisdiction

    existing = db.scalar(
        select(Jurisdiction).where(
            (Jurisdiction.code == tenant_client.client_id) | (Jurisdiction.name == tenant_client.city_name)
        )
    )
    if existing is not None:
        tenant_client.jurisdiction_id = existing.id
        db.flush()
        return existing

    base_code = _normalize_jurisdiction_code(tenant_client.client_id or tenant_client.city_name)
    code = base_code
    suffix = 1
    while db.scalar(select(Jurisdiction).where(Jurisdiction.code == code)) is not None:
        suffix += 1
        code = f"{base_code[:96]}-{suffix}"

    jurisdiction = Jurisdiction(
        code=code,
        name=tenant_client.city_name,
        department_name=tenant_client.department_name,
        public_site_title=f"{tenant_client.city_name} Zoning Verification",
        public_contact_email=tenant_client.support_email,
        public_contact_phone=tenant_client.support_phone,
        timezone="UTC",
        is_active=True,
    )
    db.add(jurisdiction)
    db.flush()
    tenant_client.jurisdiction_id = jurisdiction.id
    db.flush()
    return jurisdiction


def _build_fee_structure_response(
    tenant_client: TenantClient,
    schedule: FeeSchedule,
    items: list[FeeScheduleItem],
) -> FeeStructureResponse:
    return FeeStructureResponse(
        client=FeeStructureClientContextRead(
            id=tenant_client.id,
            client_id=tenant_client.client_id,
            clerk_organization_id=tenant_client.clerk_organization_id,
            city_name=tenant_client.city_name,
            department_name=tenant_client.department_name,
            jurisdiction_id=tenant_client.jurisdiction_id or "",
        ),
        schedule=FeeScheduleRead.model_validate(schedule),
        items=[FeeScheduleItemRead.model_validate(item) for item in items],
    )


def _build_home_page_content_response(
    tenant_client: TenantClient,
    content: dict,
) -> HomePageContentResponse:
    return HomePageContentResponse(
        client=HomePageClientContextRead(
            id=tenant_client.id,
            client_id=tenant_client.client_id,
            clerk_organization_id=tenant_client.clerk_organization_id,
            city_name=tenant_client.city_name,
            department_name=tenant_client.department_name,
            jurisdiction_id=tenant_client.jurisdiction_id or "",
        ),
        content=HomePageContentUpsert.model_validate(content),
    )


def _get_tenant_client_by_org_id(db: Session, organization_id: str) -> TenantClient:
    tenant_client = db.scalar(
        select(TenantClient).where(
            (TenantClient.id == organization_id)
            | (TenantClient.clerk_organization_id == organization_id)
            | (TenantClient.client_id == organization_id)
        )
    )
    if tenant_client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant client not found")
    return tenant_client


def _get_tenant_client_by_lookup(
    db: Session,
    *,
    organization_id: str | None = None,
    client_id: str | None = None,
) -> TenantClient:
    if organization_id:
        return _get_tenant_client_by_org_id(db, organization_id)

    if client_id:
        tenant_client = db.scalar(select(TenantClient).where(TenantClient.client_id == client_id))
        if tenant_client is not None:
            return tenant_client

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant client not found")


def _tenant_asset_dir(namespace: str, asset_type: str) -> Path:
    asset_dir = Path(settings.artifacts_dir) / "jurisdictions" / namespace / asset_type
    asset_dir.mkdir(parents=True, exist_ok=True)
    return asset_dir


def _safe_remove_asset_file(asset_path: str | None) -> None:
    if not asset_path:
        return

    if asset_path.startswith("/api/admin/assets/jurisdictions/"):
        relative = asset_path.removeprefix("/api/admin/assets/jurisdictions/")
        parts = relative.split("/", 2)
        if len(parts) != 3:
            return
        namespace, asset_type, filename = parts
        candidate = _tenant_asset_dir(namespace, asset_type) / filename
    else:
        prefix = "/api/admin/assets/tenant-logos/"
        if not asset_path.startswith(prefix):
            return
        filename = asset_path.removeprefix(prefix)
        namespace = _legacy_logo_namespace_from_filename(filename)
        if namespace is None:
            return
        candidate = _tenant_asset_dir(namespace, "logos") / filename

    try:
        candidate.resolve().relative_to(Path(settings.artifacts_dir).resolve())
    except ValueError:
        return

    if candidate.exists():
        candidate.unlink()


def _legacy_logo_namespace_from_filename(filename: str | None) -> str | None:
    if not filename:
        return None

    candidate = filename.strip()
    if len(candidate) < 37 or candidate[36] != "-":
        return None

    namespace = candidate[:36]
    try:
        UUID(namespace)
    except ValueError:
        return None
    return namespace


def _asset_path(namespace: str, asset_type: str, filename: str) -> str:
    return f"/api/admin/assets/jurisdictions/{namespace}/{asset_type}/{filename}"


def _asset_info_from_path(asset_path: str | None) -> tuple[str, str, str] | None:
    if not asset_path:
        return None

    prefix = "/api/admin/assets/jurisdictions/"
    if asset_path.startswith(prefix):
        remainder = asset_path.removeprefix(prefix)
        parts = remainder.split("/", 2)
        if len(parts) == 3:
            namespace, asset_type, filename = parts
            if namespace and asset_type and filename:
                return namespace, asset_type, filename

    legacy_prefix = "/api/admin/assets/tenant-logos/"
    if asset_path.startswith(legacy_prefix):
        filename = asset_path.removeprefix(legacy_prefix).strip()
        namespace = _legacy_logo_namespace_from_filename(filename)
        if namespace:
            return namespace, "logos", filename

    return None


@router.post("/clients", response_model=TenantClientRead, status_code=status.HTTP_201_CREATED)
def create_tenant_client(
    payload: TenantClientCreate,
    db: Session = Depends(get_db),
) -> TenantClientRead:
    existing_client = db.scalar(select(TenantClient).where(TenantClient.client_id == payload.client_id))
    if existing_client is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Client ID already exists")

    existing_org = db.scalar(
        select(TenantClient).where(TenantClient.clerk_organization_id == payload.clerk_organization_id)
    )
    if existing_org is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Clerk organization is already linked to a tenant client",
        )

    if payload.jurisdiction_id and db.get(Jurisdiction, payload.jurisdiction_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jurisdiction not found")

    tenant_client_data = payload.model_dump(exclude={"market"})
    tenant_client = TenantClient(**tenant_client_data)
    if payload.market is not None:
        tenant_client.settings_json = merge_tenant_market_settings(
            tenant_client.settings_json,
            market=payload.market,
        )
    db.add(tenant_client)
    if not tenant_client.jurisdiction_id:
        _ensure_tenant_jurisdiction(db, tenant_client)
    db.commit()
    db.refresh(tenant_client)
    invalidate_tenant_cache()
    return TenantClientRead.model_validate(tenant_client)


@router.get("/clients", response_model=list[TenantClientRead])
def list_tenant_clients(db: Session = Depends(get_db)) -> list[TenantClientRead]:
    tenant_clients = db.scalars(select(TenantClient).order_by(TenantClient.city_name.asc())).all()
    return [TenantClientRead.model_validate(item) for item in tenant_clients]


@router.get("/clients/{organization_id}", response_model=TenantClientRead)
def get_tenant_client(
    organization_id: str,
    db: Session = Depends(get_db),
) -> TenantClientRead:
    tenant_client = _get_tenant_client_by_org_id(db, organization_id)
    return TenantClientRead.model_validate(tenant_client)


@router.patch("/clients/{organization_id}", response_model=TenantClientRead)
def update_tenant_client(
    organization_id: str,
    payload: TenantClientUpdate,
    db: Session = Depends(get_db),
) -> TenantClientRead:
    tenant_client = _get_tenant_client_by_org_id(db, organization_id)
    if payload.client_id is not None:
        client_id = payload.client_id.strip()
        if not client_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Client ID is required",
            )
        existing_client = db.scalar(
            select(TenantClient).where(
                TenantClient.client_id == client_id,
                TenantClient.id != tenant_client.id,
            )
        )
        if existing_client is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Client ID already exists",
            )
        tenant_client.client_id = client_id

    if payload.city_name is not None:
        city_name = payload.city_name.strip()
        if not city_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="City name is required")
        tenant_client.city_name = city_name

    if payload.department_name is not None:
        department_name = payload.department_name.strip()
        if not department_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Department name is required",
        )
        tenant_client.department_name = department_name

    if payload.clerk_organization_id is not None:
        clerk_organization_id = payload.clerk_organization_id.strip()
        if not clerk_organization_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Clerk organization ID is required",
            )
        if settings.clerk_secret_key and get_clerk_organization(clerk_organization_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clerk organization not found")
        existing_org = db.scalar(
            select(TenantClient).where(
                TenantClient.clerk_organization_id == clerk_organization_id,
                TenantClient.id != tenant_client.id,
            )
        )
        if existing_org is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Clerk organization is already linked to another tenant client",
            )
        tenant_client.clerk_organization_id = clerk_organization_id

    if payload.path_alias is not None:
        try:
            normalized_path_alias = normalize_tenant_path_alias(payload.path_alias)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc

        existing_alias_client = next(
            (
                candidate
                for candidate in db.scalars(select(TenantClient).where(TenantClient.id != tenant_client.id)).all()
                if get_tenant_path_alias(candidate.settings_json) == normalized_path_alias
            ),
            None,
        )
        if existing_alias_client is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Path alias is already assigned to another tenant client.",
            )

        tenant_client.settings_json = merge_tenant_path_alias_settings(
            tenant_client.settings_json,
            path_alias=normalized_path_alias,
        )

    if payload.market is not None:
        tenant_client.settings_json = merge_tenant_market_settings(
            tenant_client.settings_json,
            market=payload.market,
        )

    if payload.is_active is not None:
        tenant_client.is_active = payload.is_active

    jurisdiction = None
    if tenant_client.jurisdiction_id:
        jurisdiction = db.get(Jurisdiction, tenant_client.jurisdiction_id)

    if jurisdiction is not None:
        if payload.city_name is not None:
            jurisdiction.name = tenant_client.city_name
        if payload.department_name is not None:
            jurisdiction.department_name = tenant_client.department_name
        if payload.is_active is not None:
            jurisdiction.is_active = tenant_client.is_active

    db.commit()
    db.refresh(tenant_client)
    if tenant_client.clerk_organization_id and settings.clerk_secret_key:
        clerk_updates: dict[str, str | None] = {"name": tenant_client.city_name}
        if payload.clerk_slug is not None:
            clerk_updates["slug"] = payload.clerk_slug.strip() or None
        update_clerk_organization(
            tenant_client.clerk_organization_id,
            name=clerk_updates["name"],
            slug=clerk_updates.get("slug"),
            update_slug=payload.clerk_slug is not None,
        )
    invalidate_tenant_cache()
    return TenantClientRead.model_validate(tenant_client)


@router.post("/clients/{organization_id}/logo", response_model=TenantClientRead)
async def upload_tenant_client_logo(
    organization_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> TenantClientRead:
    tenant_client = _get_tenant_client_by_org_id(db, organization_id)
    content_type = (file.content_type or "").strip().lower()
    if content_type not in ALLOWED_LOGO_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Logo must be a PNG, JPEG, WebP, or SVG image.",
        )

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Logo file is required.")
    if len(payload) > MAX_LOGO_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Logo must be 2 MB or smaller.")

    extension = LOGO_FILE_EXTENSION_BY_CONTENT_TYPE[content_type]
    filename = f"{tenant_client.id}-{token_hex(8)}{extension}"
    storage_uploaded = upload_asset(tenant_client.id, "logos", filename, payload, content_type)
    if is_asset_storage_enabled() and not storage_uploaded:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Logo upload could not be stored in S3. Please try again.",
        )
    if not storage_uploaded:
        destination = _tenant_asset_dir(tenant_client.id, "logos") / filename
        destination.write_bytes(payload)

    previous_logo_path = get_tenant_logo_path(tenant_client.settings_json)
    tenant_client.settings_json = merge_tenant_branding_settings(
        tenant_client.settings_json,
        logo_path=_asset_path(tenant_client.id, "logos", filename),
    )
    db.commit()
    db.refresh(tenant_client)
    invalidate_tenant_cache()
    previous_asset = _asset_info_from_path(previous_logo_path)
    if previous_asset is not None:
        previous_namespace, previous_asset_type, previous_filename = previous_asset
        if is_asset_storage_enabled():
            delete_asset(previous_namespace, previous_asset_type, previous_filename)
        _safe_remove_asset_file(previous_logo_path)
    return TenantClientRead.model_validate(tenant_client)


@router.delete("/clients/{organization_id}/logo", response_model=TenantClientRead)
def delete_tenant_client_logo(
    organization_id: str,
    db: Session = Depends(get_db),
) -> TenantClientRead:
    tenant_client = _get_tenant_client_by_org_id(db, organization_id)
    previous_logo_path = get_tenant_logo_path(tenant_client.settings_json)
    tenant_client.settings_json = merge_tenant_branding_settings(
        tenant_client.settings_json,
        logo_path=None,
    )
    db.commit()
    db.refresh(tenant_client)
    invalidate_tenant_cache()
    previous_asset = _asset_info_from_path(previous_logo_path)
    if previous_asset is not None:
        previous_namespace, previous_asset_type, previous_filename = previous_asset
        if is_asset_storage_enabled():
            delete_asset(previous_namespace, previous_asset_type, previous_filename)
        _safe_remove_asset_file(previous_logo_path)
    return TenantClientRead.model_validate(tenant_client)


def _serve_tenant_asset(namespace: str, asset_type: str, filename: str) -> Response | FileResponse:
    asset_path = (_tenant_asset_dir(namespace, asset_type) / filename).resolve()
    try:
        asset_path.relative_to(Path(settings.artifacts_dir).resolve())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found") from exc

    if not asset_path.exists() or not asset_path.is_file():
        s3_asset = download_asset(namespace, asset_type, filename)
        if s3_asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
        return Response(
            content=s3_asset.content,
            media_type=s3_asset.content_type,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    if is_asset_storage_enabled():
        uploaded = upload_asset(
            namespace,
            asset_type,
            filename,
            asset_path.read_bytes(),
            guess_type(filename)[0] or "application/octet-stream",
        )
        if not uploaded:
            logger.warning("Unable to backfill asset %s/%s/%s to S3.", namespace, asset_type, filename)

    return FileResponse(asset_path)


@router.get("/assets/jurisdictions/{namespace}/{asset_type}/{filename}", response_model=None)
def get_tenant_asset(namespace: str, asset_type: str, filename: str) -> Response:
    return _serve_tenant_asset(namespace, asset_type, filename)


@router.get("/assets/tenant-logos/{filename}", response_model=None)
def get_tenant_logo_asset(filename: str) -> Response:
    namespace = _legacy_logo_namespace_from_filename(filename)
    if namespace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return _serve_tenant_asset(namespace, "logos", filename)


@router.delete("/clients/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant_client(
    organization_id: str,
    db: Session = Depends(get_db),
) -> None:
    tenant_client = _get_tenant_client_by_org_id(db, organization_id)
    db.delete(tenant_client)
    db.commit()
    invalidate_tenant_cache()


def _delete_tenant_client_dependencies(db: Session, tenant_client: TenantClient) -> None:
    db.execute(delete(TenantDomain).where(TenantDomain.tenant_client_id == tenant_client.id))
    db.execute(delete(ZoningCodeSection).where(ZoningCodeSection.tenant_client_id == tenant_client.id))
    db.execute(delete(ZoningCodeDocument).where(ZoningCodeDocument.tenant_client_id == tenant_client.id))
    db.execute(delete(ZoningCodeIngestionRun).where(ZoningCodeIngestionRun.tenant_client_id == tenant_client.id))
    db.execute(delete(EmailTemplate).where(EmailTemplate.tenant_client_id == tenant_client.id))


@router.delete("/clients/{organization_id}/purge", status_code=status.HTTP_204_NO_CONTENT)
def purge_tenant_client(
    organization_id: str,
    db: Session = Depends(get_db),
) -> None:
    tenant_client = _get_tenant_client_by_org_id(db, organization_id)
    _delete_tenant_client_dependencies(db, tenant_client)
    db.delete(tenant_client)
    db.commit()
    if is_asset_storage_enabled():
        delete_asset_namespace(tenant_client.id)
    delete_clerk_organization(tenant_client.clerk_organization_id)
    invalidate_tenant_cache()


@router.get("/clients/{organization_id}/experience-settings", response_model=TenantExperienceSettingsRead)
def get_tenant_experience_settings_route(
    organization_id: str,
    db: Session = Depends(get_db),
) -> TenantExperienceSettingsRead:
    tenant_client = _get_tenant_client_by_org_id(db, organization_id)
    _, zoning_code_url = get_tenant_experience_settings(tenant_client.settings_json)
    assistant_provider_keys, assistant_model_targets = get_tenant_assistant_settings(tenant_client.settings_json)
    assistant_agent_prompts = get_tenant_assistant_agent_prompts(tenant_client.settings_json)
    assistant_disclaimer_text = get_tenant_assistant_disclaimer_text(tenant_client.settings_json)
    return TenantExperienceSettingsRead(
        zoning_code_url=zoning_code_url,
        assistant_disclaimer_text=assistant_disclaimer_text,
        assistant_provider_keys=assistant_provider_keys,
        assistant_model_targets=assistant_model_targets,
        code_default_assistant_model_targets=CODE_DEFAULT_ASSISTANT_MODEL_TARGETS,
        assistant_agent_prompts=assistant_agent_prompts,
        raw_settings_json=tenant_client.settings_json if isinstance(tenant_client.settings_json, dict) else None,
    )


@router.get("/platform/assistant-settings", response_model=PlatformAssistantSettingsRead)
def get_platform_assistant_settings_route(
    db: Session = Depends(get_db),
) -> PlatformAssistantSettingsRead:
    settings_json = get_platform_assistant_settings_json(db)
    assistant_provider_keys, assistant_model_targets = get_tenant_assistant_settings(settings_json)
    assistant_agent_prompts = get_tenant_assistant_agent_prompts(settings_json)
    assistant_disclaimer_text = (
        get_tenant_assistant_disclaimer_text(settings_json)
        if isinstance(settings_json, dict) and settings_json.get("assistant_disclaimer_text")
        else DEFAULT_ASSISTANT_DISCLAIMER_TEXT
    )
    return PlatformAssistantSettingsRead(
        assistant_disclaimer_text=assistant_disclaimer_text,
        assistant_provider_keys=assistant_provider_keys,
        assistant_model_targets=assistant_model_targets,
        code_default_assistant_model_targets=CODE_DEFAULT_ASSISTANT_MODEL_TARGETS,
        assistant_agent_prompts=assistant_agent_prompts,
        raw_settings_json=settings_json,
    )


@router.put("/platform/assistant-settings", response_model=PlatformAssistantSettingsRead)
def update_platform_assistant_settings_route(
    payload: PlatformAssistantSettingsUpdate,
    db: Session = Depends(get_db),
) -> PlatformAssistantSettingsRead:
    merged_settings = merge_tenant_experience_settings(
        get_platform_assistant_settings_json(db),
        agent_url=None,
        zoning_code_url=None,
        assistant_disclaimer_text=payload.assistant_disclaimer_text.strip()
        if payload.assistant_disclaimer_text
        else None,
        assistant_provider_keys=payload.assistant_provider_keys,
        assistant_model_targets=payload.assistant_model_targets,
        assistant_agent_prompts=payload.assistant_agent_prompts,
    )
    set_platform_assistant_settings_json(db, merged_settings)
    assistant_provider_keys, assistant_model_targets = get_tenant_assistant_settings(merged_settings)
    assistant_agent_prompts = get_tenant_assistant_agent_prompts(merged_settings)
    assistant_disclaimer_text = (
        get_tenant_assistant_disclaimer_text(merged_settings)
        if merged_settings.get("assistant_disclaimer_text")
        else DEFAULT_ASSISTANT_DISCLAIMER_TEXT
    )
    return PlatformAssistantSettingsRead(
        assistant_disclaimer_text=assistant_disclaimer_text,
        assistant_provider_keys=assistant_provider_keys,
        assistant_model_targets=assistant_model_targets,
        code_default_assistant_model_targets=CODE_DEFAULT_ASSISTANT_MODEL_TARGETS,
        assistant_agent_prompts=assistant_agent_prompts,
        raw_settings_json=merged_settings,
    )


@router.put("/clients/{organization_id}/experience-settings", response_model=TenantExperienceSettingsRead)
def update_tenant_experience_settings(
    organization_id: str,
    payload: TenantExperienceSettingsUpdate,
    db: Session = Depends(get_db),
) -> TenantExperienceSettingsRead:
    tenant_client = _get_tenant_client_by_org_id(db, organization_id)
    agent_url, _ = get_tenant_experience_settings(tenant_client.settings_json)
    merged_settings = merge_tenant_experience_settings(
        tenant_client.settings_json,
        agent_url=agent_url,
        zoning_code_url=payload.zoning_code_url.strip() if payload.zoning_code_url else None,
        assistant_disclaimer_text=payload.assistant_disclaimer_text.strip()
        if payload.assistant_disclaimer_text
        else None,
        assistant_provider_keys=payload.assistant_provider_keys,
        assistant_model_targets=payload.assistant_model_targets,
        assistant_agent_prompts=payload.assistant_agent_prompts,
    )
    tenant_client.settings_json = merged_settings
    db.commit()
    db.refresh(tenant_client)
    invalidate_tenant_cache()
    _, zoning_code_url = get_tenant_experience_settings(tenant_client.settings_json)
    assistant_provider_keys, assistant_model_targets = get_tenant_assistant_settings(tenant_client.settings_json)
    assistant_agent_prompts = get_tenant_assistant_agent_prompts(tenant_client.settings_json)
    assistant_disclaimer_text = get_tenant_assistant_disclaimer_text(tenant_client.settings_json)
    return TenantExperienceSettingsRead(
        zoning_code_url=zoning_code_url,
        assistant_disclaimer_text=assistant_disclaimer_text,
        assistant_provider_keys=assistant_provider_keys,
        assistant_model_targets=assistant_model_targets,
        code_default_assistant_model_targets=CODE_DEFAULT_ASSISTANT_MODEL_TARGETS,
        assistant_agent_prompts=assistant_agent_prompts,
        raw_settings_json=tenant_client.settings_json if isinstance(tenant_client.settings_json, dict) else None,
        debug_received_assistant_provider_keys=payload.assistant_provider_keys,
        debug_received_assistant_model_targets=payload.assistant_model_targets,
        debug_received_assistant_agent_prompts=payload.assistant_agent_prompts,
        debug_merged_settings_json=merged_settings,
    )


@router.get("/clients/{organization_id}/assistant-telemetry", response_model=AssistantTelemetryResponse)
def get_tenant_assistant_telemetry_route(
    organization_id: str,
    page: int = Query(1, ge=1),
    search: str | None = Query(default=None, max_length=255),
    db: Session = Depends(get_db),
) -> AssistantTelemetryResponse:
    _get_tenant_client_by_org_id(db, organization_id)
    telemetry = list_assistant_run_telemetry(client_id=organization_id, page=page, search=search)
    return AssistantTelemetryResponse(
        summary=AssistantTelemetrySummaryRead.model_validate(telemetry.get("summary") or {}),
        runs=[AssistantTelemetryRunRead.model_validate(run) for run in telemetry.get("runs") or []],
        pagination=telemetry.get("pagination") or {
            "page": 1,
            "page_size": 50,
            "total_runs": 0,
            "total_pages": 0,
            "has_previous": False,
            "has_next": False,
            "search": None,
        },
    )


@router.get("/clients/{organization_id}/assistant-conversations", response_model=AssistantConversationReviewResponse)
def get_tenant_assistant_conversation_review_route(
    organization_id: str,
    page: int = Query(1, ge=1),
    search: str | None = Query(default=None, max_length=255),
    conversation_id: str | None = Query(default=None, max_length=255),
    db: Session = Depends(get_db),
) -> AssistantConversationReviewResponse:
    _get_tenant_client_by_org_id(db, organization_id)
    review = list_assistant_conversation_reviews(
        client_id=organization_id,
        page=page,
        search=search,
        conversation_id=conversation_id,
    )
    return AssistantConversationReviewResponse(
        summary=AssistantConversationReviewSummaryRead.model_validate(review.get("summary") or {}),
        conversations=[AssistantConversationReviewRead.model_validate(conversation) for conversation in review.get("conversations") or []],
        pagination=review.get("pagination") or {
            "page": 1,
            "page_size": 20,
            "total_conversations": 0,
            "total_pages": 0,
            "has_previous": False,
            "has_next": False,
            "search": None,
            "conversation_id": None,
        },
    )


@router.get("/clients/{organization_id}/assistant-embed", response_model=TenantEmbedSettingsRead)
def get_tenant_assistant_embed_settings(
    organization_id: str,
    db: Session = Depends(get_db),
) -> TenantEmbedSettingsRead:
    tenant_client = _get_tenant_client_by_org_id(db, organization_id)
    embed_settings = get_tenant_embed_settings(tenant_client.settings_json)
    return TenantEmbedSettingsRead(
        is_active=embed_settings.is_active,
        allowed_origins=embed_settings.allowed_origins,
        widget_title=embed_settings.widget_title,
        launcher_label=embed_settings.launcher_label,
        accent_color=embed_settings.accent_color,
        has_secret=bool(embed_settings.secret_hash),
        created_at=embed_settings.created_at,
        updated_at=embed_settings.updated_at,
    )


@router.post("/clients/{organization_id}/assistant-embed", response_model=TenantEmbedSettingsCreateResponse)
def upsert_tenant_assistant_embed_settings(
    organization_id: str,
    payload: TenantEmbedSettingsUpdate,
    db: Session = Depends(get_db),
) -> TenantEmbedSettingsCreateResponse:
    tenant_client = _get_tenant_client_by_org_id(db, organization_id)
    secret = generate_embed_secret()
    secret_hash = hash_embed_secret(secret)
    merged_settings = merge_tenant_embed_settings(
        tenant_client.settings_json,
        secret_hash=secret_hash,
        allowed_origins=payload.allowed_origins,
        widget_title=payload.widget_title,
        launcher_label=payload.launcher_label,
        accent_color=payload.accent_color,
        is_active=payload.is_active,
    )
    tenant_client.settings_json = merged_settings
    db.commit()
    db.refresh(tenant_client)
    invalidate_tenant_cache()

    embed_settings = get_tenant_embed_settings(tenant_client.settings_json)
    return TenantEmbedSettingsCreateResponse(
        secret=secret,
        is_active=embed_settings.is_active,
        allowed_origins=embed_settings.allowed_origins,
        widget_title=embed_settings.widget_title,
        launcher_label=embed_settings.launcher_label,
        accent_color=embed_settings.accent_color,
        has_secret=bool(embed_settings.secret_hash),
        created_at=embed_settings.created_at,
        updated_at=embed_settings.updated_at,
    )


@router.post("/clients/{organization_id}/assistant-embed/preview-secret", response_model=TenantEmbedPreviewSecretResponse)
def create_tenant_assistant_embed_preview_secret(
    organization_id: str,
    db: Session = Depends(get_db),
) -> TenantEmbedPreviewSecretResponse:
    _get_tenant_client_by_org_id(db, organization_id)
    return TenantEmbedPreviewSecretResponse(secret=generate_embed_secret())


@router.post("/clients/{organization_id}/assistant-embed/preview-session", response_model=TenantEmbedPreviewSessionResponse)
def create_tenant_assistant_embed_preview_session(
    organization_id: str,
    payload: TenantEmbedPreviewSessionRequest,
    db: Session = Depends(get_db),
) -> TenantEmbedPreviewSessionResponse:
    tenant_client = _get_tenant_client_by_org_id(db, organization_id)
    embed_settings = get_tenant_embed_settings(tenant_client.settings_json)
    assistant_disclaimer_text = get_effective_assistant_disclaimer_text(
        get_platform_assistant_settings_json(db),
        tenant_client.settings_json,
    )
    normalized_origin = payload.origin.strip()
    if not normalized_origin:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid origin")

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
    return TenantEmbedPreviewSessionResponse(**response_payload)


@router.get("/clients/{organization_id}/zoning-knowledge", response_model=ZoningKnowledgeStatusRead)
def get_zoning_knowledge_status(
    organization_id: str,
    db: Session = Depends(get_db),
) -> ZoningKnowledgeStatusRead:
    tenant_client = _get_tenant_client_by_org_id(db, organization_id)
    return ZoningKnowledgeStatusRead.model_validate(build_zoning_knowledge_status(db, tenant_client))


@router.post("/clients/{organization_id}/zoning-knowledge/ingest", response_model=ZoningKnowledgeStatusRead)
def ingest_zoning_knowledge(
    organization_id: str,
    payload: ZoningKnowledgeIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ZoningKnowledgeStatusRead:
    tenant_client = _get_tenant_client_by_org_id(db, organization_id)
    try:
        run = start_zoning_code_ingestion(db, tenant_client, mode=payload.mode)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    background_tasks.add_task(run_zoning_code_ingestion, run.id)
    return ZoningKnowledgeStatusRead.model_validate(build_zoning_knowledge_status(db, tenant_client))


@router.post("/clients/{organization_id}/zoning-knowledge/query", response_model=ZoningKnowledgeQueryResponse)
def query_zoning_knowledge(
    organization_id: str,
    payload: ZoningKnowledgeQueryRequest,
    db: Session = Depends(get_db),
) -> ZoningKnowledgeQueryResponse:
    tenant_client = _get_tenant_client_by_org_id(db, organization_id)
    return ZoningKnowledgeQueryResponse.model_validate(
        query_customer_zoning_knowledge(db, tenant_client, query=payload.query, limit=payload.limit)
    )


@router.get("/jurisdictions", response_model=list[JurisdictionRead])
def list_jurisdictions(db: Session = Depends(get_db)) -> list[JurisdictionRead]:
    jurisdictions = db.scalars(select(Jurisdiction).order_by(Jurisdiction.name.asc())).all()
    return [JurisdictionRead.model_validate(item) for item in jurisdictions]


@router.post(
    "/jurisdictions",
    response_model=JurisdictionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_jurisdiction(
    payload: JurisdictionCreate,
    db: Session = Depends(get_db),
) -> JurisdictionRead:
    existing = db.scalar(select(Jurisdiction).where(Jurisdiction.code == payload.code))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Jurisdiction code already exists",
        )
    jurisdiction = Jurisdiction(**payload.model_dump())
    db.add(jurisdiction)
    db.commit()
    db.refresh(jurisdiction)
    return JurisdictionRead.model_validate(jurisdiction)


@router.get("/fees")
def get_fees(
    jurisdiction_id: str | None = Query(default=None),
    organization_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    if organization_id or client_id:
        tenant_client = _get_tenant_client_by_lookup(db, organization_id=organization_id, client_id=client_id)
        _ensure_tenant_jurisdiction(db, tenant_client)
        db.commit()
        db.refresh(tenant_client)
        schedule, items = ensure_active_fee_schedule_for_tenant(db, tenant_client)
        invalidate_tenant_cache()
        return {
            "schedules": [FeeScheduleRead.model_validate(schedule).model_dump()],
            "items": [FeeScheduleItemRead.model_validate(item).model_dump() for item in items],
        }

    schedules_stmt = select(FeeSchedule).order_by(FeeSchedule.created_at.desc())
    if jurisdiction_id:
        schedules_stmt = schedules_stmt.where(FeeSchedule.jurisdiction_id == jurisdiction_id)
    schedules = db.scalars(schedules_stmt).all()
    items_stmt = select(FeeScheduleItem).order_by(FeeScheduleItem.display_order.asc(), FeeScheduleItem.created_at.asc())
    if jurisdiction_id:
        items_stmt = items_stmt.join(FeeSchedule).where(FeeSchedule.jurisdiction_id == jurisdiction_id)
    items = db.scalars(items_stmt).all()
    return {
        "schedules": [FeeScheduleRead.model_validate(item).model_dump() for item in schedules],
        "items": [FeeScheduleItemRead.model_validate(item).model_dump() for item in items],
    }


@router.get("/fees/structure", response_model=FeeStructureResponse)
def get_fee_structure(
    organization_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> FeeStructureResponse:
    tenant_client = _get_tenant_client_by_lookup(db, organization_id=organization_id, client_id=client_id)
    cache = get_cache_service()
    cached = cache.get_json(_admin_fee_structure_cache_key(tenant_client))
    if cached is not cache.cache_miss:
        return FeeStructureResponse.model_validate(cached)

    _ensure_tenant_jurisdiction(db, tenant_client)
    db.commit()
    db.refresh(tenant_client)
    schedule, items = ensure_active_fee_schedule_for_tenant(db, tenant_client)
    invalidate_tenant_cache()
    response = _build_fee_structure_response(tenant_client, schedule, items)
    cache.set_json(
        _admin_fee_structure_cache_key(tenant_client),
        response.model_dump(mode="json"),
        ttl_seconds=settings.admin_config_cache_ttl_seconds,
    )
    return response


@router.put("/fees/structure", response_model=FeeStructureResponse)
def save_fee_structure(
    payload: FeeStructureUpsert,
    organization_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> FeeStructureResponse:
    tenant_client = _get_tenant_client_by_lookup(db, organization_id=organization_id, client_id=client_id)
    _ensure_tenant_jurisdiction(db, tenant_client)
    schedule, items = update_fee_structure_for_tenant(
        db,
        tenant_client,
        name=payload.name.strip() if payload.name else None,
        items=[item.model_dump() for item in payload.items],
    )
    invalidate_tenant_cache()
    cache = get_cache_service()
    response = _build_fee_structure_response(tenant_client, schedule, items)
    cache.set_json(
        _admin_fee_structure_cache_key(tenant_client),
        response.model_dump(mode="json"),
        ttl_seconds=settings.admin_config_cache_ttl_seconds,
    )
    return response


@router.get("/home-page-content", response_model=HomePageContentResponse)
def get_home_page_content(
    organization_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HomePageContentResponse:
    tenant_client = _get_tenant_client_by_lookup(db, organization_id=organization_id, client_id=client_id)
    cache = get_cache_service()
    cached = cache.get_json(_admin_home_page_cache_key(tenant_client))
    if cached is not cache.cache_miss:
        return HomePageContentResponse.model_validate(cached)

    _ensure_tenant_jurisdiction(db, tenant_client)
    db.commit()
    db.refresh(tenant_client)
    record = get_home_page_content_record(db, tenant_client.jurisdiction_id)
    response = _build_home_page_content_response(
        tenant_client,
        get_home_page_content_payload(record, tenant_client),
    )
    cache.set_json(
        _admin_home_page_cache_key(tenant_client),
        response.model_dump(mode="json"),
        ttl_seconds=settings.admin_config_cache_ttl_seconds,
    )
    return response


@router.put("/home-page-content", response_model=HomePageContentResponse)
def save_home_page_content(
    payload: HomePageContentUpsert,
    organization_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HomePageContentResponse:
    if not has_home_page_content_storage(db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Home page content storage is not ready. Run the "
                "20260313_000009_home_page_content migration and try again."
            ),
        )

    tenant_client = _get_tenant_client_by_lookup(db, organization_id=organization_id, client_id=client_id)
    jurisdiction = _ensure_tenant_jurisdiction(db, tenant_client)
    record = get_home_page_content_record(db, jurisdiction.id)
    normalized = payload.model_dump()

    if record is None:
        record = JurisdictionHomePageContent(
            jurisdiction_id=jurisdiction.id,
            hero_json=normalized["hero"],
            services_json=normalized["services"],
            about_json=normalized["about"],
            faq_json=normalized["faq"],
            contact_json=normalized["contact"],
        )
        db.add(record)
    else:
        record.hero_json = normalized["hero"]
        record.services_json = normalized["services"]
        record.about_json = normalized["about"]
        record.faq_json = normalized["faq"]
        record.contact_json = normalized["contact"]

    db.commit()
    db.refresh(tenant_client)
    db.refresh(record)
    invalidate_tenant_cache()
    cache = get_cache_service()
    response = _build_home_page_content_response(
        tenant_client,
        get_home_page_content_payload(record, tenant_client),
    )
    cache.set_json(
        _admin_home_page_cache_key(tenant_client),
        response.model_dump(mode="json"),
        ttl_seconds=settings.admin_config_cache_ttl_seconds,
    )
    return response


@router.post("/fees/schedules", response_model=FeeScheduleRead, status_code=status.HTTP_201_CREATED)
def create_fee_schedule(
    payload: FeeScheduleCreate,
    db: Session = Depends(get_db),
) -> FeeScheduleRead:
    if db.get(Jurisdiction, payload.jurisdiction_id) is None:
        raise HTTPException(status_code=404, detail="Jurisdiction not found")
    if payload.created_by_user_id and db.get(User, payload.created_by_user_id) is None:
        raise HTTPException(status_code=404, detail="Creator user not found")
    schedule = FeeSchedule(**payload.model_dump())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return FeeScheduleRead.model_validate(schedule)


@router.post("/fees/items", response_model=FeeScheduleItemRead, status_code=status.HTTP_201_CREATED)
def create_fee_schedule_item(
    payload: FeeScheduleItemCreate,
    db: Session = Depends(get_db),
) -> FeeScheduleItemRead:
    if db.get(FeeSchedule, payload.fee_schedule_id) is None:
        raise HTTPException(status_code=404, detail="Fee schedule not found")
    item = FeeScheduleItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return FeeScheduleItemRead.model_validate(item)


@router.get("/letter-templates", response_model=list[LetterTemplateRead])
def get_letter_templates(
    jurisdiction_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[LetterTemplateRead]:
    stmt = select(LetterTemplate).order_by(LetterTemplate.created_at.desc())
    if jurisdiction_id:
        stmt = stmt.where(LetterTemplate.jurisdiction_id == jurisdiction_id)
    templates = db.scalars(stmt).all()
    return [LetterTemplateRead.model_validate(item) for item in templates]


@router.post(
    "/letter-templates",
    response_model=LetterTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
def create_letter_template(
    payload: LetterTemplateCreate,
    db: Session = Depends(get_db),
) -> LetterTemplateRead:
    if db.get(Jurisdiction, payload.jurisdiction_id) is None:
        raise HTTPException(status_code=404, detail="Jurisdiction not found")
    if payload.created_by_user_id and db.get(User, payload.created_by_user_id) is None:
        raise HTTPException(status_code=404, detail="Creator user not found")
    template = LetterTemplate(**payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return LetterTemplateRead.model_validate(template)


@router.get("/email-templates", response_model=EmailTemplatesResponse)
def get_email_templates(
    organization_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> EmailTemplatesResponse:
    tenant_client = _get_tenant_client_by_lookup(db, organization_id=organization_id, client_id=client_id)
    effective_templates = get_effective_email_templates(db, tenant_client)
    return EmailTemplatesResponse(
        client=EmailTemplateClientContextRead(
            id=tenant_client.id,
            client_id=tenant_client.client_id,
            clerk_organization_id=tenant_client.clerk_organization_id,
            city_name=tenant_client.city_name,
            department_name=tenant_client.department_name,
        ),
        templates=[
            EmailTemplateEffectiveRead(
                id=item.template.id,
                code=item.template.code,
                trigger_state=item.template.trigger_state,
                name=item.template.name,
                description=item.template.description,
                category=item.template.category,
                subject_template=item.template.subject_template,
                body_template=item.template.body_template,
                status=item.template.status,
                version=item.template.version,
                owner_organization_id=item.template.owner_organization_id,
                default_template_id=item.default_template.id,
                override_template_id=item.override_template.id if item.override_template else None,
                is_override=item.override_template is not None,
                updated_at=item.template.updated_at,
            )
            for item in effective_templates
        ],
    )


@router.post("/email-templates/{code}", response_model=EmailTemplateEffectiveRead)
def save_email_template_override(
    code: str,
    payload: EmailTemplateOverrideUpsert,
    organization_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> EmailTemplateEffectiveRead:
    if payload.code != code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template code mismatch")

    tenant_client = _get_tenant_client_by_lookup(db, organization_id=organization_id, client_id=client_id)
    defaults = {template.code: template for template in get_default_email_templates(db)}
    default_template = defaults.get(code)
    if default_template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Default email template not found")

    override_template = db.scalar(
        select(EmailTemplate).where(
            EmailTemplate.tenant_client_id == tenant_client.id,
            EmailTemplate.code == code,
        )
    )
    if override_template is None:
        override_template = EmailTemplate(
            jurisdiction_id=tenant_client.jurisdiction_id,
            tenant_client_id=tenant_client.id,
            owner_organization_id=tenant_client.clerk_organization_id or tenant_client.client_id,
            base_template_id=default_template.id,
            code=default_template.code,
            trigger_state=default_template.trigger_state,
            name=payload.name,
            description=payload.description,
            category=payload.category,
            subject_template=payload.subject_template,
            body_template=payload.body_template,
            status=payload.status,
            version=1,
            created_by_user_id=None,
            is_system_default=False,
        )
        db.add(override_template)
    else:
        override_template.name = payload.name
        override_template.description = payload.description
        override_template.category = payload.category
        override_template.subject_template = payload.subject_template
        override_template.body_template = payload.body_template
        override_template.status = payload.status
        override_template.trigger_state = default_template.trigger_state
        override_template.owner_organization_id = tenant_client.clerk_organization_id or tenant_client.client_id
        override_template.base_template_id = default_template.id
        override_template.jurisdiction_id = tenant_client.jurisdiction_id
        override_template.version += 1

    db.commit()
    db.refresh(override_template)
    return EmailTemplateEffectiveRead(
        id=override_template.id,
        code=override_template.code,
        trigger_state=override_template.trigger_state,
        name=override_template.name,
        description=override_template.description,
        category=override_template.category,
        subject_template=override_template.subject_template,
        body_template=override_template.body_template,
        status=override_template.status,
        version=override_template.version,
        owner_organization_id=override_template.owner_organization_id,
        default_template_id=default_template.id,
        override_template_id=override_template.id,
        is_override=True,
        updated_at=override_template.updated_at,
    )


@router.delete("/email-templates/{code}/override", status_code=status.HTTP_204_NO_CONTENT)
def reset_email_template_override(
    code: str,
    organization_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> None:
    tenant_client = _get_tenant_client_by_lookup(db, organization_id=organization_id, client_id=client_id)
    override_template = db.scalar(
        select(EmailTemplate).where(
            EmailTemplate.tenant_client_id == tenant_client.id,
            EmailTemplate.code == code,
        )
    )
    if override_template is None:
        return

    db.delete(override_template)
    db.commit()


@router.get("/database-info", response_model=DatabaseInfoRead)
def get_database_info_route(db: Session = Depends(get_db)) -> DatabaseInfoRead:
    return DatabaseInfoRead.model_validate(get_database_info(db))


@router.post("/database-info/cleanup-dangling", response_model=DatabaseCleanupResultRead)
def cleanup_database_dangling_records_route(db: Session = Depends(get_db)) -> DatabaseCleanupResultRead:
    return DatabaseCleanupResultRead.model_validate(cleanup_dangling_records(db))
