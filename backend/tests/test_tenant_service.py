"""Unit tests for tenant config resolution."""

from unittest.mock import Mock

from sqlalchemy import create_engine
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Jurisdiction, TenantClient, TenantDomain
from app.services.tenant_service import (
    build_default_home_page_content,
    get_home_page_content_record,
    get_tenant_assistant_settings,
    get_tenant_assistant_agent_prompts,
    get_tenant_experience_settings,
    has_home_page_content_storage,
    invalidate_tenant_cache,
    merge_tenant_experience_settings,
    resolve_tenant_public_config,
)


def _db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_local()


def test_resolve_tenant_public_config_by_hostname_and_client_id() -> None:
    db = _db()
    try:
        jurisdiction = Jurisdiction(
            code="tenant-a",
            name="Tenant A",
            department_name="Planning & Zoning Department",
            timezone="UTC",
        )
        db.add(jurisdiction)
        db.flush()
        tenant = TenantClient(
            client_id="tenant-a",
            jurisdiction_id=jurisdiction.id,
            city_name="Tenant A",
            department_name="Planning & Zoning Department",
            standard_letter_fee_cents=10000,
            comprehensive_letter_fee_cents=20000,
            expedited_fee_cents=5000,
            support_phone="(555) 100-0000",
            support_email="tenant-a@example.com",
            contact_address="100 Main Street",
            settings_json={
                "agent_url": "https://agents.example.com/tenant-a",
                "zoning_code_url": "https://codes.example.com/tenant-a/zoning",
            },
        )
        db.add(tenant)
        db.flush()
        db.add(TenantDomain(tenant_client_id=tenant.id, hostname="tenant-a.local", is_primary=True))
        db.commit()

        invalidate_tenant_cache()
        by_host = resolve_tenant_public_config(db, host="tenant-a.local:3001")
        by_client_id = resolve_tenant_public_config(db, client_id="tenant-a")

        assert by_host is not None
        assert by_host.client_id == "tenant-a"
        assert by_host.city_name == "Tenant A"
        assert by_host.agent_url == "https://agents.example.com/tenant-a"
        assert by_client_id is not None
        assert by_client_id.support_email == "tenant-a@example.com"
        assert by_client_id.zoning_code_url == "https://codes.example.com/tenant-a/zoning"
        assert by_client_id.home_page_content["contact"]["email"] == "tenant-a@example.com"
    finally:
        db.close()


def test_merge_tenant_experience_settings_preserves_agent_url_when_updating_zoning_code_url() -> None:
    merged = merge_tenant_experience_settings(
        {
            "agent_url": "https://agents.example.com/tenant-a",
            "zoning_code_url": "https://codes.example.com/tenant-a/old",
        },
        agent_url="https://agents.example.com/tenant-a",
        zoning_code_url="https://codes.example.com/tenant-a/new",
    )

    assert get_tenant_experience_settings(merged) == (
        "https://agents.example.com/tenant-a",
        "https://codes.example.com/tenant-a/new",
    )


def test_get_tenant_assistant_settings_normalizes_legacy_customer_zoning_agent_keys() -> None:
    provider_keys, model_targets = get_tenant_assistant_settings(
        {
            "assistant_provider_keys": {"gemini": " key "},
            "assistant_model_targets": {
                "customer-zoning-agent": {
                    "provider": "unsupported",
                    "model_id": " gpt-5 ",
                    "base_url": " https://example.com ",
                },
                "customer_zoning_team": {
                    "provider": "gemini",
                    "model_id": " gemini-2.5-pro ",
                    "base_url": " https://example.com ",
                },
            },
            "assistant_agent_prompts": {
                "customer-zoning-agent": " Legacy prompt ",
                "customer-zoning-team": " Public prompt ",
                "customer_zoning_team": " New prompt ",
            },
        }
    )

    assert provider_keys["gemini"] == "key"
    assert model_targets["customer_zoning_team"]["provider"] == "gemini"
    assert model_targets["customer_zoning_team"]["model_id"] == "gemini-2.5-pro"
    assert model_targets["customer_zoning_team"]["base_url"] == "https://example.com"
    assert model_targets["customer_zoning_team"] != model_targets.get("customer-zoning-agent")

    prompts = get_tenant_assistant_agent_prompts(
        {
            "assistant_agent_prompts": {
                "customer-zoning-agent": " Legacy prompt ",
                "customer-zoning-team": " Public prompt ",
                "customer_zoning_team": " New prompt ",
            }
        }
    )

    assert prompts["customer_zoning_team"] == "New prompt"


def test_build_default_home_page_content_uses_tenant_specific_values() -> None:
    tenant = TenantClient(
        client_id="tenant-a",
        city_name="Dream Town",
        department_name="Planning & Zoning Department",
        standard_letter_fee_cents=10000,
        comprehensive_letter_fee_cents=20000,
        expedited_fee_cents=5000,
        support_email="support@dreamtown.gov",
        support_phone="555-0000",
        contact_address="100 Main Street",
    )

    content = build_default_home_page_content(tenant)

    assert content["hero"]["title"] == "Welcome to the Dream Town"
    assert content["about"]["body"].startswith("An official document from the Dream Town")
    assert content["contact"]["email"] == "support@dreamtown.gov"


def test_get_home_page_content_record_returns_none_when_table_is_missing() -> None:
    db = Mock()
    db.scalar.side_effect = ProgrammingError(
        "SELECT ...",
        {},
        Exception('relation "shared_jurisdiction_home_page_content" does not exist'),
    )

    result = get_home_page_content_record(db, "jur-1")

    assert result is None
    db.rollback.assert_called_once()


def test_has_home_page_content_storage_returns_true_for_created_schema() -> None:
    db = _db()
    try:
        assert has_home_page_content_storage(db) is True
    finally:
        db.close()
