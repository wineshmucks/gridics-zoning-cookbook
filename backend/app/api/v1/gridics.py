"""Direct Gridics proxy routes exposed from the UZone backend."""

import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.services.shared.gridics_client import _build_gridics_client

router = APIRouter()
_STATE_CODE_PATTERN = re.compile(r"\b([A-Z]{2})\b(?:\s+\d{5}(?:-\d{4})?)?(?:\b|$)")
_ZIP_CODE_PATTERN = re.compile(r"\b(\d{5})(?:-\d{4})?\b")
_STATE_NAME_TO_CODE = {
    "alabama": "al",
    "alaska": "ak",
    "arizona": "az",
    "arkansas": "ar",
    "california": "ca",
    "colorado": "co",
    "connecticut": "ct",
    "delaware": "de",
    "district of columbia": "dc",
    "florida": "fl",
    "georgia": "ga",
    "hawaii": "hi",
    "idaho": "id",
    "illinois": "il",
    "indiana": "in",
    "iowa": "ia",
    "kansas": "ks",
    "kentucky": "ky",
    "louisiana": "la",
    "maine": "me",
    "maryland": "md",
    "massachusetts": "ma",
    "michigan": "mi",
    "minnesota": "mn",
    "mississippi": "ms",
    "missouri": "mo",
    "montana": "mt",
    "nebraska": "ne",
    "nevada": "nv",
    "new hampshire": "nh",
    "new jersey": "nj",
    "new mexico": "nm",
    "new york": "ny",
    "north carolina": "nc",
    "north dakota": "nd",
    "ohio": "oh",
    "oklahoma": "ok",
    "oregon": "or",
    "pennsylvania": "pa",
    "rhode island": "ri",
    "south carolina": "sc",
    "south dakota": "sd",
    "tennessee": "tn",
    "texas": "tx",
    "utah": "ut",
    "vermont": "vt",
    "virginia": "va",
    "washington": "wa",
    "west virginia": "wv",
    "wisconsin": "wi",
    "wyoming": "wy",
}


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


def _infer_state_code_from_address(address: str | None) -> str | None:
    normalized = str(address or "").strip()
    if not normalized:
        return None

    upper_address = normalized.upper()
    code_match = _STATE_CODE_PATTERN.search(upper_address)
    if code_match:
        return code_match.group(1).lower()

    lower_address = normalized.lower()
    for state_name, state_code in _STATE_NAME_TO_CODE.items():
        if state_name in lower_address:
            return state_code

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
    lat: float = Query(...),
    lon: float = Query(...),
    state_env: str = Query(...),
) -> dict:
    try:
        client = _build_gridics_client()
        return client.get_property_record_by_coordinates(
            latitude=lat,
            longitude=lon,
            state_env=state_env,
        )        
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/property-summary")
def get_property_summary(
    lat: float = Query(...),
    lon: float = Query(...),
    state_env: str = Query(...),
) -> dict:
    rec = get_property_record(lat=lat, lon=lon, state_env=state_env)
    return _summarize_property_record(rec)
