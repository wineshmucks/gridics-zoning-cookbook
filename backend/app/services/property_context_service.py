"""Property context retrieval and normalization for Gridics-backed lookups."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.schemas.property_context import PropertyContextFact, PropertyContextResult
from app.services.citation_formatter import build_property_citation
from app.services.gridics_client import _build_gridics_client, extract_compressed_zoning_summary


class PropertyLookupAdapter(Protocol):
    """Interface for property lookup providers."""

    def get_property_record_by_coordinates(self, *, state_env: str, latitude: float, longitude: float) -> dict[str, Any]:
        ...


@dataclass(slots=True)
class GridicsPropertyContextService:
    """Fetch and normalize parcel data into a prompt-safe schema."""

    adapter: PropertyLookupAdapter | None = None

    def get_property_context(
        self,
        *,
        lat: float,
        lng: float,
        jurisdiction_id: str,
        address: str | None = None,
    ) -> PropertyContextResult:
        client = self.adapter or _build_gridics_client()
        state_env = self._state_env_from_jurisdiction(jurisdiction_id)

        try:
            raw_response = client.get_property_record_by_coordinates(
                state_env=state_env,
                latitude=lat,
                longitude=lng,
            )
        except Exception as exc:
            return PropertyContextResult(
                status="unavailable",
                jurisdiction_id=jurisdiction_id,
                address=address,
                latitude=lat,
                longitude=lng,
                error_message=str(exc),
                missing_fields=["parcel lookup"],
            )

        return self._normalize(
            jurisdiction_id=jurisdiction_id,
            address=address,
            lat=lat,
            lng=lng,
            raw_response=raw_response,
        )

    @staticmethod
    def _state_env_from_jurisdiction(jurisdiction_id: str) -> str:
        normalized = (jurisdiction_id or "").strip().lower()
        if len(normalized) == 2:
            return normalized
        if "-" in normalized:
            return normalized.rsplit("-", 1)[-1][:2]
        return normalized[:2] or "fl"

    def _normalize(
        self,
        *,
        jurisdiction_id: str,
        address: str | None,
        lat: float,
        lng: float,
        raw_response: dict[str, Any],
    ) -> PropertyContextResult:
        summary = extract_compressed_zoning_summary(raw_response)
        if summary.get("error"):
            return PropertyContextResult(
                status="partial" if raw_response.get("data") else "not_found",
                jurisdiction_id=jurisdiction_id,
                address=address,
                latitude=lat,
                longitude=lng,
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
                facts_for_prompt=self._build_prompt_facts(address=address, lat=lat, lng=lng, zoning_district=None, future_land_use=None, overlays=[]),
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
        address: str | None,
        lat: float,
        lng: float,
        zoning_district: str | None,
        future_land_use: str | None,
        overlays: list[str],
    ) -> list[PropertyContextFact]:
        facts = [
            PropertyContextFact(label="Address", value=address or "Unknown"),
            PropertyContextFact(label="Coordinates", value=f"{lat:.6f}, {lng:.6f}"),
        ]
        if zoning_district:
            facts.append(PropertyContextFact(label="Zoning district", value=zoning_district))
        if future_land_use:
            facts.append(PropertyContextFact(label="Future land use", value=future_land_use))
        if overlays:
            facts.append(PropertyContextFact(label="Overlays", value=", ".join(overlays)))
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

