"""Route coverage for admin configuration APIs."""

from __future__ import annotations

import asyncio
from io import BytesIO
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select

from app.api.v1 import admin
from app.db.models import (
    EmailTemplate,
    FeeSchedule,
    FeeScheduleItem,
    Jurisdiction,
    JurisdictionHomePageContent,
    TenantClient,
    TenantDomain,
    ZoningCodeDocument,
    ZoningCodeIngestionRun,
    ZoningCodeSection,
)
from app.schemas import (
    EmailTemplateOverrideUpsert,
    FeeScheduleCreate,
    FeeScheduleItemCreate,
    FeeStructureItemUpsert,
    FeeStructureUpsert,
    HomePageAbout,
    HomePageContact,
    HomePageContentUpsert,
    HomePageFaqItem,
    HomePageHero,
    HomePageHeroStat,
    HomePageServiceItem,
    JurisdictionCreate,
    PlatformAssistantSettingsUpdate,
    TenantClientCreate,
    TenantClientUpdate,
    TenantExperienceSettingsUpdate,
    ZoningKnowledgeIngestRequest,
    ZoningKnowledgeQueryRequest,
)

from .helpers import add_jurisdiction, add_tenant_client, add_user, make_db


class FakeCache:
    def __init__(self) -> None:
        self.cache_miss = object()
        self._store: dict[str, object] = {}

    def get_json(self, key: str):
        return self._store.get(key, self.cache_miss)

    def set_json(self, key: str, value, ttl_seconds: int | None = None) -> None:
        self._store[key] = value


class FakeUploadFile:
    def __init__(self, content_type: str, payload: bytes) -> None:
        self.content_type = content_type
        self._payload = payload

    async def read(self) -> bytes:
        return self._payload


def test_tenant_client_crud_and_asset_routes(monkeypatch, tmp_path) -> None:
    db = make_db()
    try:
        add_jurisdiction(db)
        add_user(db, id="user-admin", email="admin@example.com")
        monkeypatch.setattr(admin.settings, "clerk_secret_key", "")
        monkeypatch.setattr(admin.settings, "artifacts_dir", str(tmp_path))
        monkeypatch.setattr(admin, "invalidate_tenant_cache", lambda: None)
        monkeypatch.setattr(admin, "delete_clerk_organization", lambda organization_id: None)
        monkeypatch.setattr(admin, "is_asset_storage_enabled", lambda: False)
        monkeypatch.setattr(admin, "upload_asset", lambda *args, **kwargs: False)
        monkeypatch.setattr(admin, "delete_asset", lambda *args, **kwargs: None)
        monkeypatch.setattr(admin, "delete_asset_namespace", lambda *args, **kwargs: None)

        created = admin.create_tenant_client(
            TenantClientCreate(
                client_id="dream-town",
                clerk_organization_id="org_dream_town",
                city_name="Dream Town",
                department_name="Planning",
                jurisdiction_id="jur-1",
                market="IL",
            ),
            db=db,
        )
        assert created.client_id == "dream-town"
        assert created.jurisdiction_id == "jur-1"
        assert created.settings_json["market"] == "IL"

        listed = admin.list_tenant_clients(db=db)
        assert len(listed) == 1
        assert admin.get_tenant_client("org_dream_town", db=db).id == created.id

        updated = admin.update_tenant_client(
            "org_dream_town",
            TenantClientUpdate(
                client_id="dream-town-updated",
                city_name="Dream Town Updated",
                department_name="Planning Updated",
                path_alias="/dream-town",
                market="IL",
                is_active=False,
            ),
            db=db,
        )
        assert updated.client_id == "dream-town-updated"
        assert updated.is_active is False

        class UploadFile:
            content_type = "image/png"

            async def read(self):
                return b"png-data"

        uploaded = asyncio.run(
            admin.upload_tenant_client_logo(
                "org_dream_town",
                file=UploadFile(),
                db=db,
            )
        )
        logo_path = uploaded.settings_json["header_logo_path"]
        assert logo_path.endswith(".png")

        asset = admin.get_tenant_asset(*logo_path.removeprefix("/api/admin/assets/jurisdictions/").split("/", 2))
        assert asset.path is not None

        legacy_asset = admin.get_tenant_logo_asset(logo_path.rsplit("/", 1)[-1])
        assert legacy_asset.path is not None

        deleted_logo = admin.delete_tenant_client_logo("org_dream_town", db=db)
        assert deleted_logo.settings_json.get("header_logo_path") is None

        deleted = admin.delete_tenant_client("org_dream_town", db=db)
        assert deleted is None

        tenant_b = add_tenant_client(db, id="tenant-b", client_id="purge-town", clerk_organization_id="org_purge_town")
        db.add_all(
            [
                TenantDomain(tenant_client_id=tenant_b.id, hostname="purge.gridics.com", is_primary=True),
                ZoningCodeIngestionRun(
                    id="run-1",
                    tenant_client_id=tenant_b.id,
                    mode="ingest",
                    status="running",
                    source_url="https://example.com",
                    pages_crawled=1,
                    documents_extracted=1,
                    sections_extracted=1,
                    chunks_upserted=1,
                ),
                ZoningCodeDocument(
                    id="doc-1",
                    tenant_client_id=tenant_b.id,
                    ingestion_run_id="run-1",
                    source_url="https://example.com/code",
                    source_hash="abc",
                    raw_text="text",
                ),
                ZoningCodeSection(
                    tenant_client_id=tenant_b.id,
                    document_id="doc-1",
                    section_key="sec-1",
                    section_title="Section 1",
                    normalized_text="text",
                    content_hash="hash",
                    ingestion_run_id="run-1",
                ),
                EmailTemplate(
                    tenant_client_id=tenant_b.id,
                    owner_organization_id="org_purge_town",
                    code="request-submitted",
                    trigger_state="submitted",
                    name="Submitted",
                    category="request_updates",
                    subject_template="Subject",
                    body_template="Body",
                    status="active",
                    version=1,
                ),
            ]
        )
        db.commit()
        admin.purge_tenant_client("org_purge_town", db=db)
        assert db.get(TenantClient, tenant_b.id) is None
    finally:
        db.close()


def test_settings_and_zoning_routes(monkeypatch) -> None:
    db = make_db()
    try:
        tenant = add_tenant_client(
            db,
            settings_json={
                "zoning_code_url": "https://example.com/zoning",
                "assistant_disclaimer_text": "Use official city docs.",
                "assistant_provider_keys": {"gemini": "key-1"},
                "assistant_model_targets": {"assistant": {"provider": "gemini", "model_id": "gemini-2.0-flash-001"}},
                "assistant_agent_prompts": {"assistant": "Be helpful."},
                "assistant_embed": {
                    "is_active": True,
                    "allowed_origins": ["https://example.com"],
                    "widget_title": "Ask Dream Town",
                    "launcher_label": "Ask",
                    "accent_color": "#112233",
                },
            },
        )
        fake_cache = FakeCache()
        monkeypatch.setattr(admin, "get_cache_service", lambda: fake_cache)
        monkeypatch.setattr(admin, "invalidate_tenant_cache", lambda: None)
        monkeypatch.setattr(admin.settings, "embed_session_signing_secret", "signing-secret-0123456789abcdef0")
        monkeypatch.setattr(admin.settings, "clerk_secret_key", "")
        monkeypatch.setattr(admin, "list_assistant_run_telemetry", lambda client_id, page, search: {
            "summary": {"total_runs": 1, "input_tokens": 2, "output_tokens": 3, "total_tokens": 5, "cost": 1.25},
            "runs": [
                {
                    "id": "run-1",
                    "run_scope": "team",
                    "agent_id": "agent-1",
                    "conversation_id": "conv-1",
                    "message_id": "msg-1",
                    "run_id": "run-1",
                    "session_id": "sess-1",
                    "model_provider": "gemini",
                    "model_name": "gemini-2.0-flash-001",
                    "model_id": "gemini-2.0-flash-001",
                    "input_tokens": 2,
                    "output_tokens": 3,
                    "total_tokens": 5,
                    "cost": 1.25,
                    "time_to_first_token": 0.1,
                    "duration_seconds": 1.2,
                    "created_at": "2026-01-01T00:00:00",
                    "metrics_json": {"latency": 1},
                }
            ],
            "pagination": {"page": page, "page_size": 50, "total_runs": 1, "total_pages": 1, "has_previous": False, "has_next": False, "search": search},
        })
        monkeypatch.setattr(admin, "list_assistant_conversation_reviews", lambda client_id, page, search, conversation_id: {
            "summary": {
                "total_conversations": 1,
                "total_turns": 1,
                "total_runs": 1,
                "total_feedback": 1,
                "input_tokens": 2,
                "output_tokens": 3,
                "total_tokens": 5,
                "cost": 1.25,
            },
            "conversations": [
                {
                    "conversation_id": "conv-1",
                    "latest_at": "2026-01-01T00:00:00",
                    "turn_count": 1,
                    "run_count": 1,
                    "feedback_count": 1,
                    "input_tokens": 2,
                    "output_tokens": 3,
                    "total_tokens": 5,
                    "cost": 1.25,
                    "turns": [
                        {
                            "id": "turn-1",
                            "created_at": "2026-01-01T00:00:00",
                            "message_id": "msg-1",
                            "run_id": "run-1",
                            "agent_id": "agent-1",
                            "intent_type": "zoning",
                            "jurisdiction_status": "allowed",
                            "policy_decision": "allow",
                            "reason_code": "good",
                            "payload_json": {"ok": True},
                        }
                    ],
                    "runs": [
                        {
                            "id": "run-1",
                            "run_scope": "team",
                            "agent_id": "agent-1",
                            "conversation_id": "conv-1",
                            "message_id": "msg-1",
                            "run_id": "run-1",
                            "session_id": "sess-1",
                            "model_provider": "gemini",
                            "model_name": "gemini-2.0-flash-001",
                            "model_id": "gemini-2.0-flash-001",
                            "input_tokens": 2,
                            "output_tokens": 3,
                            "total_tokens": 5,
                            "cost": 1.25,
                            "time_to_first_token": 0.1,
                            "duration_seconds": 1.2,
                            "created_at": "2026-01-01T00:00:00",
                            "metrics_json": {"latency": 1},
                        }
                    ],
                    "feedback": [
                        {
                            "id": "fb-1",
                            "clerk_user_id": "clerk-user-1",
                            "agent_id": "agent-1",
                            "surface": "public-assistant",
                            "conversation_id": "conv-1",
                            "message_id": "msg-1",
                            "run_id": "run-1",
                            "feedback_value": "up",
                            "message_excerpt": "Great",
                            "metadata_json": {"feedback_tags": ["helpful"]},
                            "created_at": "2026-01-01T00:00:00",
                        }
                    ],
                }
            ],
            "pagination": {"page": page, "page_size": 20, "total_conversations": 1, "total_pages": 1, "has_previous": False, "has_next": False, "search": search, "conversation_id": conversation_id},
        })
        monkeypatch.setattr(admin, "build_zoning_knowledge_status", lambda db_session, tenant_client: {"client_id": tenant_client.client_id, "zoning_code_url": "https://example.com/zoning", "embedder_provider": "gemini", "embedder_model_id": "gemini-embedding-001", "embedder_dimensions": 1536, "progress_percent": 100.0, "progress_message": "Ingestion complete.", "is_complete": True, "documents": 2, "sections": 3, "chunks": 4, "latest_run": None})
        monkeypatch.setattr(admin, "start_zoning_code_ingestion", lambda db_session, tenant_client, mode: SimpleNamespace(id="run-1"))
        monkeypatch.setattr(admin, "run_zoning_code_ingestion", lambda run_id: None)
        monkeypatch.setattr(admin, "query_customer_zoning_knowledge", lambda db_session, tenant_client, query, limit: {"query": query, "results": [{"content": "Result", "name": "Section", "meta_data": {"source": "demo"}}]})

        experience = admin.get_tenant_experience_settings_route("dream-town", db=db)
        assert experience.zoning_code_url == "https://example.com/zoning"

        updated_experience = admin.update_tenant_experience_settings(
            "dream-town",
            TenantExperienceSettingsUpdate(
                zoning_code_url="https://example.com/zoning-updated",
                assistant_disclaimer_text="Verify it.",
                assistant_provider_keys={"gemini": "key-2"},
                assistant_model_targets={"assistant": {"provider": "gemini", "model_id": "gemini-2.5-flash"}},
                assistant_agent_prompts={"assistant": "Be concise."},
            ),
            db=db,
        )
        assert updated_experience.zoning_code_url == "https://example.com/zoning-updated"
        assert updated_experience.debug_received_assistant_provider_keys["gemini"] == "key-2"

        platform = admin.get_platform_assistant_settings_route(db=db)
        assert platform.assistant_disclaimer_text
        updated_platform = admin.update_platform_assistant_settings_route(
            PlatformAssistantSettingsUpdate(
                assistant_disclaimer_text="Platform-wide note.",
                assistant_provider_keys={"gemini": "platform-key"},
                assistant_model_targets={"assistant": {"provider": "gemini", "model_id": "gemini-2.0-pro"}},
                assistant_agent_prompts={"assistant": "Keep it short."},
            ),
            db=db,
        )
        assert updated_platform.assistant_disclaimer_text == "Platform-wide note."

        telemetry = admin.get_tenant_assistant_telemetry_route("dream-town", page=1, search=None, db=db)
        assert telemetry.summary.total_runs == 1
        conversations = admin.get_tenant_assistant_conversation_review_route(
            "dream-town",
            page=1,
            search=None,
            conversation_id=None,
            db=db,
        )
        assert conversations.summary.total_conversations == 1

        embed_settings = admin.get_tenant_assistant_embed_settings("dream-town", db=db)
        assert embed_settings.is_active is True
        created_embed = admin.upsert_tenant_assistant_embed_settings(
            "dream-town",
            admin.TenantEmbedSettingsUpdate(
                allowed_origins=["https://example.com"],
                widget_title="Ask Dream Town",
                launcher_label="Ask",
                accent_color="#112233",
                is_active=True,
            ),
            db=db,
        )
        assert created_embed.has_secret is True

        preview_secret = admin.create_tenant_assistant_embed_preview_secret("dream-town", db=db)
        assert preview_secret.secret.startswith("uze_")

        preview_session = admin.create_tenant_assistant_embed_preview_session(
            "dream-town",
            admin.TenantEmbedPreviewSessionRequest(origin="https://example.com"),
            db=db,
        )
        assert preview_session.client_id == "dream-town"

        status = admin.get_zoning_knowledge_status("dream-town", db=db)
        assert status.documents == 2
        queued = admin.ingest_zoning_knowledge(
            "dream-town",
            ZoningKnowledgeIngestRequest(mode="ingest"),
            background_tasks=BackgroundTasks(),
            db=db,
        )
        assert queued.latest_run is None or queued.documents == 2
        query = admin.query_zoning_knowledge(
            "dream-town",
            ZoningKnowledgeQueryRequest(query="zoning", limit=3),
            db=db,
        )
        assert query.query == "zoning"
    finally:
        db.close()


def test_jurisdiction_fee_template_and_home_page_routes(monkeypatch) -> None:
    db = make_db()
    try:
        jurisdiction = add_jurisdiction(db)
        tenant = add_tenant_client(db, jurisdiction_id=jurisdiction.id)
        fake_cache = FakeCache()
        now = datetime.now(UTC).replace(tzinfo=None)
        monkeypatch.setattr(admin, "get_cache_service", lambda: fake_cache)
        monkeypatch.setattr(admin, "invalidate_tenant_cache", lambda: None)
        monkeypatch.setattr(admin.settings, "clerk_secret_key", "")
        monkeypatch.setattr(admin, "has_home_page_content_storage", lambda db_session: True)
        monkeypatch.setattr(
            admin,
            "ensure_active_fee_schedule_for_tenant",
            lambda db_session, tenant_client: (
                FeeSchedule(
                    id="schedule-1",
                    jurisdiction_id=jurisdiction.id,
                    name="Default",
                    status="active",
                    created_by_user_id=None,
                    effective_start_at=None,
                    effective_end_at=None,
                    created_at=datetime.now(UTC).replace(tzinfo=None),
                    updated_at=datetime.now(UTC).replace(tzinfo=None),
                ),
                [
                    FeeScheduleItem(
                        id="item-1",
                        fee_schedule_id="schedule-1",
                        code="standard",
                        name="Standard",
                        category="general",
                        fee_type="fixed",
                        amount_cents=5000,
                        currency="USD",
                        display_order=0,
                        is_active=True,
                        created_at=datetime.now(UTC).replace(tzinfo=None),
                        updated_at=datetime.now(UTC).replace(tzinfo=None),
                    )
                ],
            ),
        )
        monkeypatch.setattr(
            admin,
            "update_fee_structure_for_tenant",
            lambda db_session, tenant_client, name, items: (
                FeeSchedule(
                    id="schedule-2",
                    jurisdiction_id=jurisdiction.id,
                    name=name or "Updated",
                    status="active",
                    created_by_user_id=None,
                    effective_start_at=None,
                    effective_end_at=None,
                    created_at=datetime.now(UTC).replace(tzinfo=None),
                    updated_at=datetime.now(UTC).replace(tzinfo=None),
                ),
                [
                    FeeScheduleItem(
                        id="item-2",
                        fee_schedule_id="schedule-2",
                        code=items[0]["code"],
                        name=items[0]["name"],
                        category=items[0]["category"],
                        fee_type=items[0]["fee_type"],
                        amount_cents=items[0]["amount_cents"],
                        currency=items[0]["currency"],
                        display_order=items[0]["display_order"],
                        is_active=items[0]["is_active"],
                        created_at=datetime.now(UTC).replace(tzinfo=None),
                        updated_at=datetime.now(UTC).replace(tzinfo=None),
                    )
                ],
            ),
        )
        monkeypatch.setattr(
            admin,
            "get_default_email_templates",
            lambda db_session: [
                EmailTemplate(
                    id="default-email-1",
                    jurisdiction_id=None,
                    tenant_client_id=None,
                    owner_organization_id=None,
                    base_template_id=None,
                    code="request-submitted",
                    trigger_state="submitted",
                    name="Request Submitted",
                    description="Default template",
                    category="request_updates",
                    subject_template="Subject",
                    body_template="Body",
                    status="active",
                    version=1,
                    is_system_default=True,
                    created_at=now,
                    updated_at=now,
                )
            ],
        )
        monkeypatch.setattr(
            admin,
            "get_effective_email_templates",
            lambda db_session, tenant_client: [
                SimpleNamespace(
                    template=EmailTemplate(
                        id="default-email-1",
                        jurisdiction_id=None,
                        tenant_client_id=None,
                        owner_organization_id=None,
                        base_template_id=None,
                        code="request-submitted",
                        trigger_state="submitted",
                        name="Request Submitted",
                        description="Default template",
                        category="request_updates",
                        subject_template="Subject",
                        body_template="Body",
                        status="active",
                        version=1,
                        is_system_default=True,
                        created_at=now,
                        updated_at=now,
                    ),
                    default_template=EmailTemplate(
                        id="default-email-1",
                        jurisdiction_id=None,
                        tenant_client_id=None,
                        owner_organization_id=None,
                        base_template_id=None,
                        code="request-submitted",
                        trigger_state="submitted",
                        name="Request Submitted",
                        description="Default template",
                        category="request_updates",
                        subject_template="Subject",
                        body_template="Body",
                        status="active",
                        version=1,
                        is_system_default=True,
                        created_at=now,
                        updated_at=now,
                    ),
                    override_template=None,
                )
            ],
        )

        jurisdictions = admin.list_jurisdictions(db=db)
        assert jurisdictions
        created_jurisdiction = admin.create_jurisdiction(
            JurisdictionCreate(code="new-town", name="New Town", department_name="Planning"),
            db=db,
        )
        assert created_jurisdiction.code == "new-town"

        fees = admin.get_fees(jurisdiction_id=None, organization_id="org_dream_town", client_id=None, db=db)
        assert fees["schedules"][0]["name"] == "Default"
        fee_structure = admin.get_fee_structure(organization_id="org_dream_town", client_id=None, db=db)
        assert fee_structure.schedule.name == "Default"
        updated_fee_structure = admin.save_fee_structure(
            FeeStructureUpsert(
                name="Updated",
                items=[
                    FeeStructureItemUpsert(
                        code="standard",
                        name="Standard Updated",
                        category="general",
                        fee_type="fixed",
                        amount_cents=6000,
                    )
                ],
            ),
            organization_id="org_dream_town",
            client_id=None,
            db=db,
        )
        assert updated_fee_structure.schedule.name == "Updated"

        homepage = admin.get_home_page_content(organization_id="org_dream_town", client_id=None, db=db)
        assert homepage.client.client_id == tenant.client_id
        saved_homepage = admin.save_home_page_content(
            HomePageContentUpsert(
                hero=HomePageHero(
                    badge="Official City Documentation",
                    title="Welcome to Dream Town",
                    subtitle="Visit our zoning portal.",
                    primary_button_text="Start Request",
                    secondary_button_text="Ask Assistant",
                    learn_more_text="Learn more",
                    stats=[HomePageHeroStat(label="Processing", value="2 days", icon="◔")],
                ),
                services=[
                    HomePageServiceItem(
                        id="zvl",
                        title="Zoning Verification Letters",
                        description="Official zoning documentation.",
                        processing_time="2 days",
                        fee="$25",
                    )
                ],
                about=HomePageAbout(title="About", body="About body"),
                faq=[HomePageFaqItem(id="faq-1", question="Question?", answer="Answer.")],
                contact=HomePageContact(title="Need help?", body="Contact us.", email="help@example.com"),
            ),
            organization_id="org_dream_town",
            client_id=None,
            db=db,
        )
        assert saved_homepage.client.client_id == tenant.client_id

        schedule = admin.create_fee_schedule(
            FeeScheduleCreate(jurisdiction_id=jurisdiction.id, name="New Schedule", status="draft"),
            db=db,
        )
        assert schedule.jurisdiction_id == jurisdiction.id
        item = admin.create_fee_schedule_item(
            FeeScheduleItemCreate(
                fee_schedule_id=schedule.id,
                code="base",
                name="Base Fee",
                fee_type="fixed",
                amount_cents=7500,
            ),
            db=db,
        )
        assert item.fee_schedule_id == schedule.id

        templates = admin.get_letter_templates(jurisdiction_id=None, db=db)
        assert templates == []
        letter_template = admin.create_letter_template(
            admin.LetterTemplateCreate(
                jurisdiction_id=jurisdiction.id,
                code="standard-letter",
                name="Standard Letter",
                letter_type="standard",
                status="draft",
                template_body="Hello",
            ),
            db=db,
        )
        assert letter_template.code == "standard-letter"

        email_templates = admin.get_email_templates(organization_id="org_dream_town", client_id=None, db=db)
        assert email_templates.client.client_id == tenant.client_id
        saved_email_template = admin.save_email_template_override(
            "request-submitted",
            EmailTemplateOverrideUpsert(
                code="request-submitted",
                name="Request Submitted Override",
                subject_template="Subject override",
                body_template="Body override",
                status="active",
            ),
            organization_id="org_dream_town",
            client_id=None,
            db=db,
        )
        assert saved_email_template.is_override is True
        admin.reset_email_template_override("request-submitted", organization_id="org_dream_town", client_id=None, db=db)
    finally:
        db.close()
