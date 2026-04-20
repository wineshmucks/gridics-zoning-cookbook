"""Route coverage for public tenant configuration APIs."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import HTTPException

from app.api.v1 import public
from app.core.security import AuthContext
from app.db.models import AssistantMessageFeedback, TenantClient
from app.services.embed_service import hash_embed_secret

from .helpers import add_jurisdiction, add_tenant_client, make_db


def test_assistant_feedback_can_create_update_and_delete(monkeypatch) -> None:
    db = make_db()
    try:
        tenant = add_tenant_client(db)
        auth = AuthContext(provider="clerk", user_id="clerk-user-1", session_id="sess-1", email="user@example.com")

        created = public.upsert_assistant_feedback(
            public.AssistantMessageFeedbackUpsertRequest(
                client_id=tenant.client_id,
                agent_id="agent-1",
                conversation_id="conv-1",
                message_id="msg-1",
                feedback_value="up",
                message_excerpt="Great answer.",
                feedback_tags=["helpful", " "],
            ),
            db=db,
            auth=auth,
        )
        assert created["feedback_value"] == "up"
        from sqlalchemy import select

        feedback = db.scalar(
            select(AssistantMessageFeedback).where(
                AssistantMessageFeedback.tenant_client_id == tenant.id,
                AssistantMessageFeedback.conversation_id == "conv-1",
                AssistantMessageFeedback.message_id == "msg-1",
            )
        )
        assert feedback is not None
        assert feedback.clerk_user_id == "clerk-user-1"

        updated = public.upsert_assistant_feedback(
            public.AssistantMessageFeedbackUpsertRequest(
                client_id=tenant.client_id,
                agent_id="agent-2",
                conversation_id="conv-1",
                message_id="msg-1",
                feedback_value="down",
                feedback_tags=["bug"],
            ),
            db=db,
            auth=auth,
        )
        assert updated["feedback_value"] == "down"

        removed = public.upsert_assistant_feedback(
            public.AssistantMessageFeedbackUpsertRequest(
                client_id=tenant.client_id,
                agent_id="agent-2",
                conversation_id="conv-1",
                message_id="msg-1",
                feedback_value=None,
            ),
            db=db,
            auth=auth,
        )
        assert removed["feedback_value"] is None
    finally:
        db.close()


def test_client_config_path_alias_and_customer_listing(monkeypatch) -> None:
    db = make_db()
    try:
        add_jurisdiction(db)
        tenant = add_tenant_client(
            db,
            settings_json={
                "path_alias": "/dream-town",
                "header_logo_path": "/api/admin/assets/jurisdictions/tenant-a/logos/logo.png",
                "assistant_embed": {
                    "secret_hash": hash_embed_secret("embed-secret"),
                    "allowed_origins": ["https://example.com"],
                    "widget_title": "Ask Dream Town",
                    "launcher_label": "Have a question?",
                    "accent_color": "#112233",
                    "is_active": True,
                },
            },
        )
        add_tenant_client(
            db,
            id="tenant-2",
            client_id="hidden-town",
            clerk_organization_id="org_hidden",
            city_name="Hidden Town",
            department_name="Planning",
            settings_json={},
        )
        add_tenant_client(
            db,
            id="tenant-3",
            client_id="gridics",
            clerk_organization_id="org_gridics",
            city_name="Gridics",
            department_name="Ops",
            settings_json={},
        )
        monkeypatch.setattr(public.settings, "gridics_clerk_organization_id", "org_gridics")
        monkeypatch.setattr(public, "clerk_organization_exists", lambda organization_id: organization_id == "org_dream_town")

        def fake_resolve(db_session, *, client_id=None, organization_id=None, path_alias=None, host=None):
            if client_id == tenant.client_id or path_alias == "/dream-town":
                return SimpleNamespace(
                    client_id=tenant.client_id,
                    clerk_organization_id="org_dream_town",
                    city_name="Dream Town",
                    department_name="Planning",
                    public_site_title=None,
                    path_alias="/dream-town",
                    logo_path="/api/admin/assets/jurisdictions/tenant-a/logos/logo.png",
                    logo_source="jurisdiction",
                    standard_letter_fee_cents=7500,
                    comprehensive_letter_fee_cents=15000,
                    expedited_fee_cents=5000,
                    support_phone=None,
                    support_email=None,
                    contact_address=None,
                    jurisdiction_id="jur-1",
                    agent_url=None,
                    zoning_code_url=None,
                    market=None,
                    assistant_disclaimer_text="Verify before relying.",
                    home_page_content={},
                    surface_configs={},
                )
            return None

        monkeypatch.setattr(public, "resolve_tenant_public_config", fake_resolve)
        monkeypatch.setattr(
            public,
            "tenant_public_config_to_dict",
            lambda config: {
                "client_id": config.client_id,
                "city_name": config.city_name,
                "path_alias": config.path_alias,
                "logo_path": config.logo_path,
                "logo_source": config.logo_source,
            },
        )

        config = public.get_client_config(
            request=SimpleNamespace(headers={"host": "agentic.gridics.com"}),
            clientid=tenant.client_id,
            orgid=None,
            path_alias=None,
            host=None,
            db=db,
        )
        assert config["client_id"] == tenant.client_id

        customers = public.list_public_customers(db=db)
        assert customers == [
                {
                    "orgid": "org_dream_town",
                    "client_id": "dream-town",
                    "path_alias": "/dream-town",
                    "logo_path": "/api/admin/assets/jurisdictions/tenant-a/logos/logo.png",
                    "logo_source": "jurisdiction",
                    "city_name": "Dream Town",
                    "department_name": "Planning",
                }
        ]

        alias = public.resolve_path_alias(path="/dream-town", db=db)
        assert alias["orgid"] == "org_dream_town"

        try:
            public.resolve_path_alias(path="/admin", db=db)
        except HTTPException as exc:
            assert exc.status_code == 422
        else:
            raise AssertionError("Reserved aliases should be rejected.")

        try:
            public.get_client_config(
                request=SimpleNamespace(headers={}),
                clientid=None,
                orgid=None,
                path_alias=None,
                host=None,
                db=db,
            )
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("Missing tenant config should return 404.")
    finally:
        db.close()


def test_client_config_can_backfill_tenant_from_organization(monkeypatch) -> None:
    db = make_db()
    try:
        calls = {"count": 0}

        def fake_resolve(db_session, *, client_id, organization_id, path_alias, host):
            calls["count"] += 1
            if calls["count"] == 1:
                return None
            return SimpleNamespace(
                client_id="org-new",
                clerk_organization_id="org-new",
                city_name="New City",
                department_name="Planning",
                public_site_title=None,
                path_alias=None,
                logo_path=None,
                standard_letter_fee_cents=0,
                comprehensive_letter_fee_cents=0,
                expedited_fee_cents=0,
                support_phone=None,
                support_email=None,
                contact_address=None,
                jurisdiction_id=None,
                agent_url=None,
                zoning_code_url=None,
                market=None,
                assistant_disclaimer_text="",
                home_page_content={},
                surface_configs={},
            )

        monkeypatch.setattr(public, "resolve_tenant_public_config", fake_resolve)
        monkeypatch.setattr(public, "_ensure_tenant_client_for_organization", lambda db_session, organization_id: TenantClient(id="tenant-1", client_id="org-new", clerk_organization_id=organization_id, city_name="New City", department_name="Planning", standard_letter_fee_cents=0, comprehensive_letter_fee_cents=0, expedited_fee_cents=0))
        monkeypatch.setattr(public, "tenant_public_config_to_dict", lambda config: {"client_id": config.client_id, "city_name": config.city_name})

        response = public.get_client_config(
            request=SimpleNamespace(headers={}),
            clientid=None,
            orgid="org-new",
            path_alias=None,
            host=None,
            db=db,
        )
        assert response["client_id"] == "org-new"
        assert calls["count"] == 2
    finally:
        db.close()


def test_embed_session_routes_cover_create_and_read(monkeypatch) -> None:
    db = make_db()
    try:
        tenant = add_tenant_client(
            db,
            settings_json={
                "assistant_embed": {
                    "secret_hash": hash_embed_secret("embed-secret"),
                    "allowed_origins": ["https://example.com"],
                    "widget_title": "Ask Dream Town",
                    "launcher_label": "Have a question?",
                    "accent_color": "#112233",
                    "is_active": True,
                },
                "assistant_disclaimer_text": "Verify before relying.",
            },
        )
        monkeypatch.setattr(public.settings, "embed_session_signing_secret", "signing-secret-0123456789abcdef0")

        response = public.create_embed_session(
            payload=public.EmbedSessionCreateRequest(client_id=tenant.client_id, origin="https://example.com"),
            db=db,
            embed_secret="embed-secret",
        )
        assert response["client_id"] == tenant.client_id
        assert response["origin"] == "https://example.com"

        read_response = public.read_embed_session(request=SimpleNamespace(headers={"x-uzone-embed-token": response["token"]}))
        assert read_response["client_id"] == tenant.client_id

        try:
            public.create_embed_session(
                payload=public.EmbedSessionCreateRequest(client_id=tenant.client_id, origin="https://example.com"),
                db=db,
                embed_secret="wrong-secret",
            )
        except HTTPException as exc:
            assert exc.status_code == 401
        else:
            raise AssertionError("Bad embed secrets should be rejected.")

        try:
            public.read_embed_session(request=SimpleNamespace(headers={}))
        except HTTPException as exc:
            assert exc.status_code == 401
        else:
            raise AssertionError("Missing embed tokens should be rejected.")
    finally:
        db.close()
