"""Property context retrieval and normalization for Gridics-backed lookups."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.schemas.property_context import PropertyContextFact, PropertyContextResult
from app.services.shared.citation_formatter import build_property_citation
from app.services.shared.gridics_client import _build_gridics_client, extract_compressed_zoning_summary


class PropertyLookupAdapter(Protocol):
    """Interface for property lookup providers."""

    def get_property_record_by_coordinates(self, *, latitude: float, longitude: float, state_env: str) -> dict[str, Any]:
        ...

    def get_property_record(self, *, state_code: str, address: str, zip_code: str) -> dict[str, Any]:
        ...


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


@dataclass(slots=True)
class GridicsPropertyContextService:
    """Fetch and normalize parcel data into a prompt-safe schema."""

    adapter: PropertyLookupAdapter | None = None

    def get_property_context(
        self,
        *,
        lat: float,
        lng: float,
        state_env: str,
        jurisdiction_id: str,
        jurisdiction_name: str | None = None,
        address: str | None = None,
    ) -> PropertyContextResult:
        print(
            "[GridicsPropertyContextService] Fetching property context for coordinates: "
            f"({lat}, {lng}) in jurisdiction {jurisdiction_name} (ID: {jurisdiction_id}) "
            f"state_env={state_env}"
        )
        client = self.adapter or _build_gridics_client()
        
        raw_response = client.get_property_record_by_coordinates(
            latitude=lat,
            longitude=lng,
            state_env=state_env,
        )
        print(f'[GridicsPropertyContextService] response successfully retrieved from adapter/client: {bool(raw_response)}')

        return self._normalize(
            jurisdiction_id=jurisdiction_id,
            jurisdiction_name=jurisdiction_name,
            address=address,
            lat=lat,
            lng=lng,
            state_env=state_env,
            raw_response=raw_response,
        )
    

    def _normalize(
        self,
        *,
        jurisdiction_id: str,
        jurisdiction_name: str | None,
        address: str | None,
        lat: float,
        lng: float,
        state_env: str,
        raw_response: dict[str, Any],
    ) -> PropertyContextResult:
        summary = extract_compressed_zoning_summary(raw_response)
        if summary.get("error"):
            return PropertyContextResult(
                status="partial" if raw_response.get("data") else "not_found",
                jurisdiction_id=jurisdiction_id,
                jurisdiction_name=jurisdiction_name,
                address=address,
                latitude=lat,
                longitude=lng,
                state_env=state_env,
                raw_response=raw_response,
                error_message=str(summary["error"]),
                missing_fields=["zoning envelope", "allowed uses"],
                citations=[
                    build_property_citation(
                        citation_id="property-data-1",
                        label="Gridics property data",
                        address=address,
                        metadata={"status": "partial"},
                    )
                ],
                facts_for_prompt=self._build_prompt_facts(
                    jurisdiction_name=jurisdiction_name,
                    address=address,
                    lat=lat,
                    lng=lng,
                    zoning_district=None,
                    future_land_use=None,
                    overlays=[],
                ),
            )

        property_info = summary.get("property_info") or {}
        dimensions = summary.get("dimensional_standards") or {}
        setbacks = dimensions.get("setbacks_ft") or {}
        allowed_use_rows = summary.get("allowed_uses") or []
        overlays = [str(item).strip() for item in summary.get("overlays") or [] if str(item).strip()]
        missing_fields: list[str] = []

        zoning_district = self._as_text(summary.get("zoning_classification"))
        if not zoning_district:
            missing_fields.append("zoning district")
        max_height_ft = self._as_float(dimensions.get("max_height_ft"))
        if max_height_ft is None:
            missing_fields.append("height")

        facts = self._build_prompt_facts(
            jurisdiction_name=jurisdiction_name,
            address=address or self._as_text(property_info.get("address")),
            lat=lat,
            lng=lng,
            zoning_district=zoning_district,
            future_land_use=None,
            overlays=overlays,
        )

        return PropertyContextResult(
            status="success" if not missing_fields else "partial",
            jurisdiction_id=jurisdiction_id,
            jurisdiction_name=jurisdiction_name,
            address=address or self._as_text(property_info.get("address")),
            latitude=lat,
            longitude=lng,
            parcel_id=self._as_text(property_info.get("folio_number")),
            zoning_district=zoning_district,
            overlays=overlays,
            lot_area_sqft=self._as_float(dimensions.get("lot_area_sqft")),
            lot_area_acres=self._as_float(dimensions.get("lot_area_acres")),
            allowed_uses=[
                self._as_text(row.get("use"))
                for row in allowed_use_rows
                if isinstance(row, dict) and self._as_text(row.get("use"))
            ],
            setbacks_ft={
                "front_principal": self._as_float(setbacks.get("front_principal")),
                "front_secondary": self._as_float(setbacks.get("front_secondary")),
                "side": self._as_float(setbacks.get("side")),
                "rear": self._as_float(setbacks.get("rear")),
            },
            max_height_ft=max_height_ft,
            max_height_stories=self._as_float(dimensions.get("max_height_stories")),
            max_far=self._as_float(dimensions.get("max_far")),
            max_density_units=self._as_float(dimensions.get("max_density_units")),
            raw_response=raw_response,
            missing_fields=missing_fields,
            facts_for_prompt=facts,
            citations=[
                build_property_citation(
                    citation_id="property-data-1",
                    label="Gridics property data",
                    address=address or self._as_text(property_info.get("address")),
                    metadata={"status": "success" if not missing_fields else "partial"},
                )
            ],
        )

    @staticmethod
    def _build_prompt_facts(
        *,
        jurisdiction_name: str | None,
        address: str | None,
        lat: float,
        lng: float,
        zoning_district: str | None,
        future_land_use: str | None,
        overlays: list[str],
        # NEW: Pass the parsed dimensions and allowed uses down
        dimensions: dict[str, Any] = None, 
        allowed_use_rows: list[dict[str, Any]] = None,
    ) -> list[PropertyContextFact]:
        facts: list[PropertyContextFact] = []
        if jurisdiction_name:
            facts.append(PropertyContextFact(label="Jurisdiction", value=jurisdiction_name))
        facts.extend(
            [
                PropertyContextFact(label="Address", value=address or "Unknown"),
                PropertyContextFact(label="Coordinates", value=f"{lat:.6f}, {lng:.6f}"),
            ]
        )
        if zoning_district:
            facts.append(PropertyContextFact(label="Zoning District", value=zoning_district))
        if future_land_use:
            facts.append(PropertyContextFact(label="Future Land Use", value=future_land_use))
        if overlays:
            facts.append(PropertyContextFact(label="Overlays", value=", ".join(overlays)))

        # NEW: Extract allowed uses into a compact string
        if allowed_use_rows:
            allowed = [row.get("use") for row in allowed_use_rows if isinstance(row, dict) and row.get("use")]
            if allowed:
                facts.append(PropertyContextFact(label="Allowed Uses", value=", ".join(allowed)))

        # NEW: Extract critical envelope dimensions
        if dimensions:
            if dimensions.get("max_height_ft"):
                facts.append(PropertyContextFact(label="Max Height (ft)", value=str(dimensions.get("max_height_ft"))))
            if dimensions.get("max_far"):
                 facts.append(PropertyContextFact(label="Max FAR", value=str(dimensions.get("max_far"))))
            
            # Setbacks
            setbacks = dimensions.get("setbacks_ft") or {}
            if setbacks.get("front_principal"):
                facts.append(PropertyContextFact(label="Front Setback (Principal)", value=f"{setbacks.get('front_principal')} ft"))
            if setbacks.get("rear"):
                 facts.append(PropertyContextFact(label="Rear Setback", value=f"{setbacks.get('rear')} ft"))
            if setbacks.get("side"):
                 facts.append(PropertyContextFact(label="Side Setback", value=f"{setbacks.get('side')} ft"))

        return facts

    @staticmethod
    def _as_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
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
