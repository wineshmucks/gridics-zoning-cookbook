"""Direct Gridics proxy routes exposed from the UZone backend."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.services.gridics_client import _build_gridics_client

router = APIRouter()


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _first_numeric(*values: Any) -> float | int | None:
    for value in values:
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, list) and value:
            nested = _first_numeric(*value)
            if nested is not None:
                return nested
        if isinstance(value, str):
            stripped = value.replace(",", "").strip()
            try:
                return float(stripped)
            except ValueError:
                continue
    return None


def _find_key_like(value: Any, candidates: set[str]) -> Any:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = "".join(ch for ch in str(key).lower() if ch.isalnum())
            if normalized_key in candidates and nested not in (None, ""):
                return nested
        for nested in value.values():
            found = _find_key_like(nested, candidates)
            if found not in (None, ""):
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_key_like(nested, candidates)
            if found not in (None, ""):
                return found
    return None


def _summarize_property_record(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload, dict) else None
    row = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else {}
    buildings = row.get("Buildings") if isinstance(row, dict) else None
    building = buildings[0] if isinstance(buildings, list) and buildings and isinstance(buildings[0], dict) else {}
    zoning = building.get("ZoningAllowance") if isinstance(building, dict) and isinstance(building.get("ZoningAllowance"), dict) else {}
    envelope = building.get("Envelope") if isinstance(building, dict) and isinstance(building.get("Envelope"), dict) else {}
    uses_stats = building.get("UsesStatistic") if isinstance(building, dict) and isinstance(building.get("UsesStatistic"), dict) else {}

    overlays = [
        str(overlay.get("Name")).strip()
        for overlay in (building.get("Overlays") or [])
        if isinstance(overlay, dict) and str(overlay.get("Name") or "").strip()
    ]
    allowed_uses = [
        str(use.get("CalibrationUsesLabel") or use.get("TypeName") or "").strip()
        for use in (building.get("Uses") or [])
        if isinstance(use, dict)
        and str(use.get("AllowedUsesName") or "").strip().lower() == "allowed"
        and str(use.get("CalibrationUsesLabel") or use.get("TypeName") or "").strip()
    ]

    land_use = _find_key_like(
        payload,
        {
            "futurelanduse",
            "futurelandusename",
            "futurelandusedesignation",
            "futurelandusecategory",
            "landuse",
            "landusename",
            "existinglanduse",
            "existinglandusename",
        },
    )
    if not land_use:
        for overlay in overlays:
            normalized_overlay = overlay.lower()
            if "future land use" in normalized_overlay:
                land_use = overlay
                for prefix in ("City Future Land Use", "Future Land Use"):
                    if str(land_use).lower().startswith(prefix.lower()):
                        land_use = str(land_use)[len(prefix):].strip(" :-")
                        break
                break
    display_overlays = [overlay for overlay in overlays if "future land use" not in overlay.lower()]

    return {
        "address": ", ".join(
            str(part).strip()
            for part in (row.get("Address"), row.get("City"), row.get("State"), row.get("ZipCode"))
            if str(part or "").strip()
        ),
        "folio_number": row.get("FolioNumber"),
        "group_id": row.get("GroupId"),
        "zoning_code": zoning.get("ZoneCombinationName"),
        "zoning_regulation_name": zoning.get("ZoningRegulationName"),
        "zoning_regulation_link": zoning.get("ZoningRegulationLink"),
        "land_use": land_use,
        "typology": zoning.get("BuildingTypologyId"),
        "overlays": display_overlays[:4],
        "max_far": _first_numeric(envelope.get("FloorAreaRatio"), envelope.get("FloorAreaRatioCapacity")),
        "max_units": _first_numeric(envelope.get("DensityUnits")),
        "max_height_ft": _first_numeric(envelope.get("TotalBuildingHeightFeet"), envelope.get("TotalBuidingHeight")),
        "lot_area_sqft": _first_numeric(envelope.get("LotAreaFeet")),
        "allowed_use_count": _first_present(uses_stats.get("allowed"), len(allowed_uses) if allowed_uses else None),
        "allowed_uses": list(dict.fromkeys(allowed_uses))[:3],
    }


@router.get("/property-record")
def get_property_record(
    state_env: str = Query(...),
    address: str | None = Query(None),
    zip_code: str | None = Query(None, alias="zipCode"),
    lat: float | None = Query(None),
    lon: float | None = Query(None),
) -> dict:
    try:
        client = _build_gridics_client()
        if isinstance(lat, (float, int)) and isinstance(lon, (float, int)):
            return client.get_property_record_by_coordinates(
                state_env=state_env,
                latitude=lat,
                longitude=lon,
            )
        if address is None:
            raise ValueError("Provide either lat and lon, or address and zipCode.")
        if zip_code is None:
            raise ValueError("zipCode is required when address lookup is used.")
        return client.get_property_record(
            state_env=state_env,
            address=address,
            zip_code=zip_code,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/property-summary")
def get_property_summary(
    state_env: str = Query(...),
    lat: float = Query(...),
    lon: float = Query(...),
) -> dict:
    try:
        client = _build_gridics_client()
        payload = client.get_property_record_by_coordinates(
            state_env=state_env,
            latitude=lat,
            longitude=lon,
        )
        return _summarize_property_record(payload)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
