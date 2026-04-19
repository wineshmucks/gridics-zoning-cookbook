"""Route coverage for super-admin database maintenance APIs."""

from __future__ import annotations

from app.api.v1 import admin
from app.db.models import Property, TenantClient

from .helpers import add_jurisdiction, add_tenant_client, make_db


def test_database_info_and_cleanup_routes() -> None:
    db = make_db()
    try:
        add_jurisdiction(db, id="jur-valid", code="valid-town", name="Valid Town")
        add_tenant_client(
            db,
            id="tenant-valid",
            client_id="valid-town",
            clerk_organization_id="org_valid",
            jurisdiction_id="jur-valid",
        )
        add_tenant_client(
            db,
            id="tenant-dangling",
            client_id="dangling-town",
            clerk_organization_id="org_dangling",
            jurisdiction_id="missing-jur",
        )
        db.add(
            Property(
                id="prop-dangling",
                jurisdiction_id="missing-jur",
                source_system="gridics",
                source_property_id="source-1",
                group_id=None,
                apn="APN-1",
                address_line1="100 Main Street",
                address_line2=None,
                city="Dangling Town",
                state="IL",
                postal_code="12345",
                latitude=39.78,
                longitude=-89.64,
            )
        )
        db.commit()

        info = admin.get_database_info_route(db=db)
        assert info.total_size_bytes is None or info.total_size_bytes >= 0
        assert any(table.table_name == "shared_tenant_clients" for table in info.dangling_tables)
        assert any(table.table_name == "shared_properties" for table in info.dangling_tables)

        cleanup = admin.cleanup_database_dangling_records_route(db=db)
        deleted_tables = {item.table_name for item in cleanup.deleted_by_table}
        assert cleanup.deleted_rows_total > 0
        assert "shared_tenant_clients" in deleted_tables
        assert "shared_properties" in deleted_tables
        assert db.get(TenantClient, "tenant-dangling") is None
        assert db.get(Property, "prop-dangling") is None
        assert db.get(TenantClient, "tenant-valid") is not None
    finally:
        db.close()
