"""Unit tests for tenant config resolution."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Jurisdiction, TenantClient, TenantDomain
from app.services.tenant_service import (
    get_tenant_experience_settings,
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
