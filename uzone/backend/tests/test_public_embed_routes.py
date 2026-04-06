"""Tests for public embed session routes."""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import TenantClient
from app.services.embed_service import hash_embed_secret


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_local()


def test_create_and_read_embed_session(monkeypatch) -> None:
    from app.api.v1 import public

    db = _db()
    monkeypatch.setattr(public.settings, "embed_session_signing_secret", "signing-secret")
    tenant = TenantClient(
        client_id="dream-town",
        clerk_organization_id="org_dream_town",
        city_name="Dream Town",
        department_name="Planning",
        standard_letter_fee_cents=0,
        comprehensive_letter_fee_cents=0,
        expedited_fee_cents=0,
        settings_json={
            "assistant_disclaimer_text": "Please verify everything.",
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
    db.add(tenant)
    db.commit()

    try:
        response = public.create_embed_session(
            payload=public.EmbedSessionCreateRequest(client_id="dream-town", origin="https://example.com"),
            db=db,
            embed_secret="embed-secret",
        )

        assert response["client_id"] == "dream-town"
        assert response["city_name"] == "Dream Town"
        assert response["assistant_disclaimer_text"] == "Please verify everything."
        assert response["origin"] == "https://example.com"
        assert response["widget_title"] == "Ask Dream Town"

        session_response = public.read_embed_session(
            request=SimpleNamespace(headers={"x-uzone-embed-token": response["token"]})
        )
        assert session_response["client_id"] == "dream-town"
        assert session_response["assistant_disclaimer_text"] == "Please verify everything."
        assert session_response["origin"] == "https://example.com"
    finally:
        db.close()


def test_create_embed_preview_secret() -> None:
    from app.api.v1 import admin

    db = _db()
    tenant = TenantClient(
        client_id="dream-town",
        clerk_organization_id="org_dream_town",
        city_name="Dream Town",
        department_name="Planning",
        standard_letter_fee_cents=0,
        comprehensive_letter_fee_cents=0,
        expedited_fee_cents=0,
        settings_json={},
    )
    db.add(tenant)
    db.commit()

    try:
        response = admin.create_tenant_assistant_embed_preview_secret(
            organization_id="dream-town",
            db=db,
        )
        assert isinstance(response.secret, str)
        assert response.secret.startswith("uze_")
    finally:
        db.close()
