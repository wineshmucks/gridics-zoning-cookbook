"""Shared Gridics API client used by cookbook examples."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List


def _get_gridics_api_key() -> str:
    key = os.getenv("GRIDICS_API_KEY", "").strip() or os.getenv("GRIDICS_CONSUMER_KEY", "").strip()
    if not key:
        raise ValueError("Set GRIDICS_API_KEY (or GRIDICS_CONSUMER_KEY)")
    return key


@dataclass
class GridicsClient:
    api_key: str
    base_url: str = "https://api.gridics.com/v1"
    timeout_seconds: int = 20
    call_log: List[Dict[str, Any]] = field(default_factory=list)

    def _build_url(self, path: str, params: Dict[str, Any]) -> str:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        return url

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = self._build_url(path, params)
        trace_entry: Dict[str, Any] = {
            "request": {
                "method": "GET",
                "path": path,
                "url": url,
                "params": {k: v for k, v in params.items() if v is not None},
                "headers": {
                    "x-api-key": "***redacted***",
                    "accept": "application/json",
                },
            }
        }

        req = urllib.request.Request(url, method="GET")
        req.add_header("x-api-key", self.api_key)
        req.add_header("accept", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
                parsed = json.loads(body) if body else {}
                trace_entry["response"] = {
                    "status_code": getattr(resp, "status", 200),
                    "body": body,
                    "json": parsed,
                }
                self.call_log.append(trace_entry)
                return parsed
        except urllib.error.HTTPError as e:
            payload = e.read().decode("utf-8", errors="replace")
            trace_entry["response"] = {"status_code": e.code, "body": payload}
            self.call_log.append(trace_entry)
            raise RuntimeError(f"Gridics HTTP {e.code}: {payload}") from e
        except urllib.error.URLError as e:
            trace_entry["error"] = f"Gridics connection error: {e.reason}"
            self.call_log.append(trace_entry)
            raise RuntimeError(f"Gridics connection error: {e.reason}") from e

    def get_markets(self) -> Dict[str, Any]:
        return self._get("/markets", {})

    def get_property_record(self, state_code: str, address: str, zip_code: str) -> Dict[str, Any]:
        return self._get(
            "/property-record",
            {"state_env": state_code, "address": address, "zipCode": zip_code},
        )

    def get_property_record_by_coordinates(self, latitude: float, longitude: float) -> Dict[str, Any]:
        return self._get(
            "/property-record",
            {"lat": latitude, "lon": longitude},
        )

    def get_property_record_by_group_id(self, state_code: str, group_id: str) -> Dict[str, Any]:
        return self._get(
            "/property-record",
            {"state_env": state_code, "groupId": group_id},
        )

    def _normalize_search_polygon(self, search_polygon: Any) -> str:
        parsed: Any = search_polygon
        if isinstance(search_polygon, str):
            raw = search_polygon.strip()
            if not raw:
                raise ValueError("search_polygon cannot be empty")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return raw

        if isinstance(parsed, dict):
            if parsed.get("type") == "Polygon":
                parsed = parsed.get("coordinates")
            else:
                parsed = parsed.get("coordinates", parsed)

        if not isinstance(parsed, list):
            raise ValueError(
                "search_polygon must be either a Polygon GeoJSON object or a coordinates array."
            )

        return json.dumps(parsed, separators=(",", ":"))

    def search(self, search_polygon: str, page: int = 1) -> Dict[str, Any]:
        normalized_polygon = self._normalize_search_polygon(search_polygon)
        return self._get("/search", {"searchPolygon": normalized_polygon, "page": page})


def _build_gridics_client() -> GridicsClient:
    return GridicsClient(api_key=_get_gridics_api_key())


# --- DATA EXTRACTION ---

def extract_compressed_zoning_summary(raw_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strips map coordinates and HTML bloat from the Gridics API response,
    returning a lightweight dictionary for the LLM session state.
    """
    if not raw_response.get("data"):
        return {"error": "No property data found"}
        
    data_row = raw_response["data"][0]
    
    if not data_row.get("Buildings"):
        return {"error": "No building/zoning data attached to this parcel"}
        
    building = data_row["Buildings"][0]
    envelope = building.get("Envelope", {})
    
    # 1. Basic Property Info
    property_info = {
        "address": f"{data_row.get('Address', '')}, {data_row.get('City', '')}, {data_row.get('State', '')} {data_row.get('ZipCode', '')}".strip(", "),
        "folio_number": data_row.get("FolioNumber")
    }
    
    # 2. Base Zoning
    zoning_allowance = building.get("ZoningAllowance", {})
    zoning_classification = zoning_allowance.get("ZoneCombinationName", "Unknown")
    
    # 3. Overlays (Just the names, ignore the heavy HTML descriptions)
    overlays = [overlay.get("Name") for overlay in building.get("Overlays", []) if overlay.get("Name")]
    
    # 4. Dimensional Standards (Envelope constraints)
    dimensional_standards = {
        "lot_area_sqft": envelope.get("LotAreaFeet"),
        "lot_area_acres": envelope.get("LotAreaAcres"),
        "max_density_units": envelope.get("DensityUnits"),
        "max_height_stories": envelope.get("TotalBuidingHeight"),
        "max_height_ft": envelope.get("TotalBuildingHeightFeet"),
        "max_building_area_sqft": envelope.get("MaxBuildingAreaAllowed"),
        "max_far": envelope.get("FloorAreaRatio"),
        "max_lot_coverage_pct": envelope.get("LotCoverage"),
        "min_open_space_pct": envelope.get("MinOpenSpace"),
        "setbacks_ft": {
            "front_principal": envelope.get("EffectivePFrontSetbackPrincipal"),
            "front_secondary": envelope.get("EffectivePFrontSetbackSecondary"),
            "side": envelope.get("EffectivePSideSetback"),
            "rear": envelope.get("EffectivePRearSetback")
        }
    }
    
    # 5. Allowed Uses (Strip out the HTML descriptions)
    allowed_uses = []
    for use in building.get("Uses", []):
        allowed_uses.append({
            "category": use.get("TypeName"),
            "use": use.get("CalibrationUsesLabel"),
            "allowance": use.get("AllowedUsesName")
        })
        
    return {
        "property_info": property_info,
        "zoning_classification": zoning_classification,
        "overlays": overlays,
        "dimensional_standards": dimensional_standards,
        "allowed_uses": allowed_uses
    }
