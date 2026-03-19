"""Admin routes."""

import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.db.models import (
    EmailTemplate,
    FeeSchedule,
    FeeScheduleItem,
    Jurisdiction,
    JurisdictionHomePageContent,
    LetterTemplate,
    TenantClient,
    User,
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
    LetterTemplateCreate,
    LetterTemplateRead,
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
from app.services.email_template_service import get_default_email_templates, get_effective_email_templates
from app.services.cache_service import get_cache_service
from app.services.fee_service import ensure_active_fee_schedule_for_tenant, update_fee_structure_for_tenant
from app.services.tenant_service import (
    get_home_page_content_record,
    get_home_page_content_payload,
    get_tenant_assistant_settings,
    get_tenant_experience_settings,
    has_home_page_content_storage,
    invalidate_tenant_cache,
    merge_tenant_experience_settings,
)
from app.services.zoning_knowledge_service import (
    build_zoning_knowledge_status,
    run_zoning_code_ingestion,
    start_zoning_code_ingestion,
    query_customer_zoning_knowledge,
)

router = APIRouter()


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
            (TenantClient.clerk_organization_id == organization_id) | (TenantClient.client_id == organization_id)
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

    tenant_client = TenantClient(**payload.model_dump())
    db.add(tenant_client)
    if not tenant_client.jurisdiction_id:
        _ensure_tenant_jurisdiction(db, tenant_client)
    db.commit()
    db.refresh(tenant_client)
    invalidate_tenant_cache()
    return TenantClientRead.model_validate(tenant_client)


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
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="City name is required")
        tenant_client.city_name = city_name

    if payload.department_name is not None:
        department_name = payload.department_name.strip()
        if not department_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Department name is required",
        )
        tenant_client.department_name = department_name

    if payload.clerk_organization_id is not None:
        clerk_organization_id = payload.clerk_organization_id.strip()
        if not clerk_organization_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Clerk organization ID is required",
            )
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
    invalidate_tenant_cache()
    return TenantClientRead.model_validate(tenant_client)


@router.delete("/clients/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant_client(
    organization_id: str,
    db: Session = Depends(get_db),
) -> None:
    tenant_client = _get_tenant_client_by_org_id(db, organization_id)
    db.delete(tenant_client)
    db.commit()
    invalidate_tenant_cache()


@router.get("/clients/{organization_id}/experience-settings", response_model=TenantExperienceSettingsRead)
def get_tenant_experience_settings_route(
    organization_id: str,
    db: Session = Depends(get_db),
) -> TenantExperienceSettingsRead:
    tenant_client = _get_tenant_client_by_org_id(db, organization_id)
    _, zoning_code_url = get_tenant_experience_settings(tenant_client.settings_json)
    assistant_provider_keys, assistant_model_targets = get_tenant_assistant_settings(tenant_client.settings_json)
    return TenantExperienceSettingsRead(
        zoning_code_url=zoning_code_url,
        assistant_provider_keys=assistant_provider_keys,
        assistant_model_targets=assistant_model_targets,
        raw_settings_json=tenant_client.settings_json if isinstance(tenant_client.settings_json, dict) else None,
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
        assistant_provider_keys=payload.assistant_provider_keys,
        assistant_model_targets=payload.assistant_model_targets,
    )
    tenant_client.settings_json = merged_settings
    db.commit()
    db.refresh(tenant_client)
    invalidate_tenant_cache()
    _, zoning_code_url = get_tenant_experience_settings(tenant_client.settings_json)
    assistant_provider_keys, assistant_model_targets = get_tenant_assistant_settings(tenant_client.settings_json)
    return TenantExperienceSettingsRead(
        zoning_code_url=zoning_code_url,
        assistant_provider_keys=assistant_provider_keys,
        assistant_model_targets=assistant_model_targets,
        raw_settings_json=tenant_client.settings_json if isinstance(tenant_client.settings_json, dict) else None,
        debug_received_assistant_provider_keys=payload.assistant_provider_keys,
        debug_received_assistant_model_targets=payload.assistant_model_targets,
        debug_merged_settings_json=merged_settings,
    )


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
