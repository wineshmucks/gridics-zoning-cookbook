"""Route coverage for core backend APIs."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select

from app.api.v1 import auth, dev, documents, gridics, health, properties, reports
from app.core.security import AuthContext
from app.db.models import LetterVersion, Property
from app.schemas import LoginRequest, PropertyCreate, PropertySnapshotCreate, RegisterRequest

from .helpers import add_jurisdiction, add_property, add_property_snapshot, add_request, add_user, make_db, make_temp_pdf


def test_health_routes_and_route_map(monkeypatch) -> None:
    monkeypatch.setattr(health.settings, "enable_agent_os", True)
    monkeypatch.setattr(health.settings, "require_agent_os", False)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(agent_os_enabled=True)))

    assert health.health() == {"status": "ok"}
    assert health.root_health() == {"status": "ok"}
    assert health.agent_os_health(request).status_code == 200
    assert "agent_os" in health.routes()

    request.app.state.agent_os_enabled = False
    response = health.agent_os_health(request)
    assert response.status_code == 503
    assert "unavailable" in response.body.decode()


def test_dev_identities_switches_with_auth_provider(monkeypatch) -> None:
    db = make_db()
    try:
        add_user(db, email="admin@uzone.example.com", id="user-admin")
        add_user(db, email="staff@uzone.example.com", id="user-staff")
        add_user(db, email="customer@uzone.example.com", id="user-customer")

        monkeypatch.setattr(dev.settings, "auth_provider", "local")
        result = dev.dev_identities(db)
        assert result == {
            "admin_user_id": "user-admin",
            "staff_user_id": "user-staff",
            "customer_user_id": "user-customer",
        }

        monkeypatch.setattr(dev.settings, "auth_provider", "clerk")
        try:
            dev.dev_identities(db)
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("dev_identities should be unavailable outside local auth.")
    finally:
        db.close()


def test_gridics_property_record_proxy_success_and_failure(monkeypatch) -> None:
    class FakeClient:
        def get_property_record(self, *, state_env: str, address: str, zip_code: str) -> dict:
            return {"state_env": state_env, "address": address, "zip_code": zip_code}

        def get_property_record_by_coordinates(self, *, state_env: str, latitude: float, longitude: float) -> dict:
            return {"state_env": state_env, "latitude": latitude, "longitude": longitude}

    monkeypatch.setattr(gridics, "_build_gridics_client", lambda: FakeClient())
    assert gridics.get_property_record("il", "100 Main", "12345") == {
        "state_env": "il",
        "address": "100 Main",
        "zip_code": "12345",
    }
    assert gridics.get_property_record("fl", None, None, 25.728, -80.243) == {
        "state_env": "fl",
        "latitude": 25.728,
        "longitude": -80.243,
    }

    def _boom():
        raise RuntimeError("upstream failed")

    monkeypatch.setattr(gridics, "_build_gridics_client", _boom)
    try:
        gridics.get_property_record("il", "100 Main", "12345")
    except HTTPException as exc:
        assert exc.status_code == 502
    else:
        raise AssertionError("Gridics proxy should translate errors into a 502.")


def test_gridics_property_summary_uses_coordinates_and_extracts_card_fields(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        def get_property_record_by_coordinates(self, *, state_env: str, latitude: float, longitude: float) -> dict:
            captured["coordinates"] = {
                "state_env": state_env,
                "latitude": latitude,
                "longitude": longitude,
            }
            return {
                "data": [
                    {
                        "Address": "3148 MARY ST # 1",
                        "City": "Miami",
                        "State": "FL",
                        "ZipCode": "33133",
                        "FolioNumber": "0141210900010",
                        "GroupId": "2223af79c5324f8fe",
                        "Buildings": [
                            {
                                "ZoningAllowance": {
                                    "ZoneCombinationName": "T3-O",
                                    "ZoningRegulationName": "Miami 21 Code",
                                    "ZoningRegulationLink": "https://codehub.gridics.com/us/fl/miami",
                                    "BuildingTypologyId": None,
                                },
                                "Envelope": {
                                    "FloorAreaRatio": "0.8",
                                    "DensityUnits": 3,
                                    "TotalBuildingHeightFeet": 25,
                                    "LotAreaFeet": "9,200",
                                },
                                "Overlays": [
                                    {"Name": "City Future Land Use Duplex Residential"},
                                    {"Name": "NCD-3 Coconut Grove"},
                                    {"Name": "Transit Corridor"},
                                ],
                                "UsesStatistic": {"allowed": 10},
                                "Uses": [
                                    {"AllowedUsesName": "Allowed", "CalibrationUsesLabel": "Single-family"},
                                    {"AllowedUsesName": "Allowed", "CalibrationUsesLabel": "Single-family"},
                                    {"AllowedUsesName": "Not Allowed", "CalibrationUsesLabel": "Industrial"},
                                ],
                            }
                        ],
                    }
                ]
            }

    monkeypatch.setattr(gridics, "_build_gridics_client", lambda: FakeClient())

    result = gridics.get_property_summary("fl", 25.732787, -80.239989)

    assert captured["coordinates"] == {
        "state_env": "fl",
        "latitude": 25.732787,
        "longitude": -80.239989,
    }
    assert result == {
        "address": "3148 MARY ST # 1, Miami, FL, 33133",
        "folio_number": "0141210900010",
        "group_id": "2223af79c5324f8fe",
        "zoning_code": "T3-O",
        "zoning_regulation_name": "Miami 21 Code",
        "zoning_regulation_link": "https://codehub.gridics.com/us/fl/miami",
        "land_use": "Duplex Residential",
        "typology": None,
        "overlays": ["NCD-3 Coconut Grove", "Transit Corridor"],
        "max_far": 0.8,
        "max_units": 3,
        "max_height_ft": 25,
        "lot_area_sqft": 9200.0,
        "allowed_use_count": 10,
        "allowed_uses": ["Single-family"],
    }


def test_gridics_property_summary_prefers_explicit_land_use_field(monkeypatch) -> None:
    payload = {
        "data": [
            {
                "Address": "100 MAIN ST",
                "City": "Miami",
                "State": "FL",
                "ZipCode": "33130",
                "FutureLandUse": "Urban Core",
                "Buildings": [
                    {
                        "ZoningAllowance": {"ZoneCombinationName": "T6-8-O"},
                        "Envelope": {},
                        "Overlays": [{"Name": "City Future Land Use Duplex Residential"}, {"Name": "TOD Area"}],
                        "UsesStatistic": {},
                        "Uses": [],
                    }
                ],
            }
        ]
    }

    result = gridics._summarize_property_record(payload)

    assert result["land_use"] == "Urban Core"
    assert result["overlays"] == ["TOD Area"]


def test_gridics_property_summary_translates_upstream_errors(monkeypatch) -> None:
    def _boom():
        raise RuntimeError("upstream failed")

    monkeypatch.setattr(gridics, "_build_gridics_client", _boom)

    try:
        gridics.get_property_summary("fl", 25.7, -80.2)
    except HTTPException as exc:
        assert exc.status_code == 502
        assert "upstream failed" in str(exc.detail)
    else:
        raise AssertionError("Gridics summary should translate upstream errors into a 502.")


def test_download_document_success_and_missing_cases(tmp_path: Path) -> None:
    db = make_db()
    try:
        make_temp_pdf(tmp_path / "letter.pdf")
        request = add_request(db)
        version = LetterVersion(
            id="ver-1",
            request_id=request.id,
            draft_id=None,
            version_number=1,
            version_type="signed_pdf",
            html_body="<p>Letter</p>",
            pdf_storage_key=str(tmp_path / "letter.pdf"),
            pdf_sha256="abc",
            signed_by_user_id=None,
        )
        db.add(version)
        db.commit()

        file_response = documents.download_document("ver-1", db)
        assert Path(file_response.path) == tmp_path / "letter.pdf"

        try:
            documents.download_document("missing", db)
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("Missing documents should return 404.")

        db.get(LetterVersion, "ver-1").pdf_storage_key = str(tmp_path / "missing.pdf")
        db.commit()
        try:
            documents.download_document("ver-1", db)
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("Missing files should return 404.")
    finally:
        db.close()


def test_property_routes_cover_create_search_snapshot_and_lookup() -> None:
    db = make_db()
    try:
        add_jurisdiction(db)
        add_user(db)

        created = properties.create_property(
            PropertyCreate(
                jurisdiction_id="jur-1",
                source_system="gridics",
                source_property_id="source-1",
                group_id="group-1",
                apn="APN-1",
                address_line1="100 Main Street",
                address_line2=None,
                city="Dream Town",
                state="IL",
                postal_code="12345",
                latitude=39.78,
                longitude=-89.64,
            ),
            db=db,
        )
        assert created.address_line1 == "100 Main Street"

        try:
            properties.create_property(
                PropertyCreate(
                    jurisdiction_id="missing",
                    source_system="gridics",
                    address_line1="100 Main Street",
                    city="Dream Town",
                    state="IL",
                ),
                db=db,
            )
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("Unknown jurisdictions should fail property creation.")

        second = add_property(db, id="prop-2", apn="APN-2", group_id="group-2")
        results = properties.search_properties(q="APN-2", db=db)
        assert [item.id for item in results] == [second.id]
        assert properties.search_properties(q=None, jurisdiction_id="jur-1", db=db)

        snapshot = properties.create_property_snapshot(
            created.id,
            PropertySnapshotCreate(
                property_id=created.id,
                captured_by_user_id="user-1",
                capture_reason="manual",
                address="100 Main Street",
                apn="APN-1",
                group_id="group-1",
                zoning_code="R-1",
                zoning_name="Residential",
                lot_size_sf=12345,
            ),
            db=db,
        )
        assert snapshot.property_id == created.id

        try:
            properties.create_property_snapshot(
                "prop-2",
                PropertySnapshotCreate(
                    property_id="prop-1",
                    capture_reason="manual",
                    address="100 Main Street",
                ),
                db=db,
            )
        except HTTPException as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("Path/body property mismatch should fail.")

        try:
            properties.get_property("missing", db=db)
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("Unknown properties should return 404.")
    finally:
        db.close()


def test_reports_summary_counts_paid_revenue() -> None:
    db = make_db()
    try:
        add_jurisdiction(db)
        add_user(db)
        add_property(db)
        add_property_snapshot(db)
        submitted_request = add_request(db, status="submitted", payment_status="unpaid")
        submitted_request.total_amount_cents = 2500
        db.commit()
        paid_request = add_request(db, id="req-2", public_id="ZVL-2026-000002", status="paid", payment_status="paid")
        paid_request.total_amount_cents = 5000
        db.commit()

        summary = reports.reports_summary(db)
        assert summary.total_requests == 2
        assert summary.submitted_requests == 1
        assert summary.paid_requests == 1
        assert summary.total_revenue_cents == 5000
    finally:
        db.close()


def test_auth_routes_cover_register_login_and_me(monkeypatch) -> None:
    db = make_db()
    try:
        monkeypatch.setattr(auth.settings, "auth_provider", "local")

        user = auth.register(
            RegisterRequest(
                email="new@example.com",
                password="password123",
                first_name="New",
                last_name="User",
            ),
            db=db,
        )
        assert user.email == "new@example.com"

        try:
            auth.register(
                RegisterRequest(
                    email="new@example.com",
                    password="password123",
                    first_name="New",
                    last_name="User",
                ),
                db=db,
            )
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("Duplicate registrations should be rejected.")

        session = auth.login(LoginRequest(email="new@example.com", password="password123"), db=db)
        assert session.user.email == "new@example.com"
        assert session.token

        monkeypatch.setattr(
            auth,
            "sync_user_from_auth",
            lambda session_db, auth_ctx: add_user(session_db, id="user-clerk", email="clerk@example.com"),
        )
        me_result = auth.me(
            AuthContext(
                provider="clerk",
                user_id="clerk-user",
                session_id="session-1",
                email="clerk@example.com",
            ),
            db=db,
        )
        assert me_result["local_user_id"] == "user-clerk"

        monkeypatch.setattr(auth.settings, "auth_provider", "clerk")
        try:
            auth.login(LoginRequest(email="new@example.com", password="password123"), db=db)
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("Local login should be disabled under Clerk auth.")
    finally:
        db.close()
