"""Tests for public customer selection routes."""

from __future__ import annotations

import importlib
import sys
import types

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Jurisdiction, JurisdictionHomePageContent, TenantClient


def _load_public_module():
    stub_dependencies = types.ModuleType("app.api.dependencies")
    stub_dependencies.get_db = lambda: None
    stub_dependencies.get_optional_auth_context = lambda: None
    sys.modules["app.api.dependencies"] = stub_dependencies
    sys.modules.pop("app.api.v1.public", None)
    return importlib.import_module("app.api.v1.public")


def _db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_local()


def test_list_public_customers_excludes_customers_without_clerk_org_id(monkeypatch) -> None:
    public = _load_public_module()
    db = _db()
    original_gridics_org_id = public.settings.gridics_clerk_organization_id
    try:
        public.settings.gridics_clerk_organization_id = None
        db.add_all(
            [
                TenantClient(
                    client_id="dream-town",
                    clerk_organization_id=None,
                    city_name="City of Dream Town",
                    department_name="Planning",
                    standard_letter_fee_cents=7500,
                    comprehensive_letter_fee_cents=15000,
                    expedited_fee_cents=5000,
                ),
                TenantClient(
                    client_id="sunnyvale",
                    clerk_organization_id="org_sunnyvale",
                    city_name="City of Sunnyvale",
                    department_name="Planning",
                    standard_letter_fee_cents=7500,
                    comprehensive_letter_fee_cents=15000,
                    expedited_fee_cents=5000,
                ),
            ]
        )
        db.commit()

        monkeypatch.setattr(public, "clerk_organization_exists", lambda organization_id: True)

        result = public.list_public_customers(db)

        assert result == [
            {
                "orgid": "org_sunnyvale",
                "client_id": "sunnyvale",
                "path_alias": None,
                "logo_path": None,
                "city_name": "City of Sunnyvale",
                "department_name": "Planning",
            }
        ]
    finally:
        public.settings.gridics_clerk_organization_id = original_gridics_org_id
        db.close()


def test_list_public_customers_excludes_missing_clerk_organizations(monkeypatch) -> None:
    public = _load_public_module()
    db = _db()
    original_gridics_org_id = public.settings.gridics_clerk_organization_id
    try:
        public.settings.gridics_clerk_organization_id = "org_gridics"
        db.add_all(
            [
                TenantClient(
                    client_id="sunnyvale",
                    clerk_organization_id="org_sunnyvale",
                    city_name="City of Sunnyvale",
                    department_name="Planning",
                    standard_letter_fee_cents=7500,
                    comprehensive_letter_fee_cents=15000,
                    expedited_fee_cents=5000,
                ),
                TenantClient(
                    client_id="old-town",
                    clerk_organization_id="org_oldtown",
                    city_name="Old Town",
                    department_name="Planning",
                    standard_letter_fee_cents=7500,
                    comprehensive_letter_fee_cents=15000,
                    expedited_fee_cents=5000,
                ),
                TenantClient(
                    client_id="gridics",
                    clerk_organization_id="org_gridics",
                    city_name="Gridics",
                    department_name="Ops",
                    standard_letter_fee_cents=7500,
                    comprehensive_letter_fee_cents=15000,
                    expedited_fee_cents=5000,
                ),
            ]
        )
        db.commit()

        monkeypatch.setattr(
            public,
            "clerk_organization_exists",
            lambda organization_id: organization_id == "org_sunnyvale",
        )

        result = public.list_public_customers(db)

        assert result == [
            {
                "orgid": "org_sunnyvale",
                "client_id": "sunnyvale",
                "path_alias": None,
                "logo_path": None,
                "city_name": "City of Sunnyvale",
                "department_name": "Planning",
            }
        ]
    finally:
        public.settings.gridics_clerk_organization_id = original_gridics_org_id
        db.close()


def test_get_client_config_includes_jurisdiction_home_page_content() -> None:
    public = _load_public_module()
    db = _db()
    jurisdiction = Jurisdiction(
        id="jur-1",
        code="dream-town",
        name="Dream Town",
        department_name="Planning",
        timezone="UTC",
    )
    db.add(jurisdiction)
    tenant = TenantClient(
        id="tenant-1",
        client_id="dream-town",
        clerk_organization_id="org_dream_town",
        jurisdiction_id=jurisdiction.id,
        city_name="Dream Town",
        department_name="Planning",
        standard_letter_fee_cents=7500,
        comprehensive_letter_fee_cents=15000,
        expedited_fee_cents=5000,
    )
    db.add(tenant)
    db.add(
        JurisdictionHomePageContent(
            jurisdiction_id=jurisdiction.id,
            hero_json={
                "badge": "Official City Documentation",
                "title": "Welcome to Dream Town",
                "subtitle": "Configured hero copy",
                "primary_button_text": "Start Request",
                "secondary_button_text": "Ask Assistant",
                "learn_more_text": "Learn More",
                "stats": [{"label": "Processing Time", "value": "2 days", "icon": "◔"}],
            },
            services_json=[
                {
                    "id": "zvl",
                    "title": "Zoning Verification Letters",
                    "description": "Official zoning documentation.",
                    "processing_time": "2 days",
                    "fee": "$25",
                }
            ],
            about_json={"title": "About", "body": "Configured about copy"},
            faq_json=[{"id": "faq-1", "question": "Question?", "answer": "Answer."}],
            contact_json={
                "title": "Need help?",
                "body": "Configured contact copy",
                "email": "help@dreamtown.gov",
                "phone": "555-0000",
                "address": "100 Main Street",
            },
        )
    )
    db.commit()

    try:
        result = public.get_client_config(
            request=types.SimpleNamespace(headers={}),
            clientid="dream-town",
            orgid=None,
            host=None,
            db=db,
        )

        assert result["home_page_content"]["hero"]["title"] == "Welcome to Dream Town"
        assert result["home_page_content"]["contact"]["email"] == "help@dreamtown.gov"
    finally:
        db.close()
