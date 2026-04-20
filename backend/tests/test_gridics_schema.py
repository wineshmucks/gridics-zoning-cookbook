"""Tests for Gridics response normalization."""

from __future__ import annotations

from app.schemas.gridics import GridicsZoningAllowance


def test_gridics_zoning_allowance_coerces_numeric_sub_zone_id() -> None:
    allowance = GridicsZoningAllowance.model_validate(
        {
            "ZoneId": "T3",
            "SubZoneId": 0,
            "ZoneTypeId": "L",
            "BuildingTypologyId": None,
            "ZoningRegulationName": "Miami 21 Code",
            "ZoningRegulationLink": "https://codehub.gridics.com/us/fl/miami",
            "ZoneCombinationName": "T3-L",
        }
    )

    assert allowance.SubZoneId == "0"


def test_gridics_zoning_allowance_coerces_numeric_zone_type_id() -> None:
    allowance = GridicsZoningAllowance.model_validate(
        {
            "ZoneId": "CI",
            "SubZoneId": 0,
            "ZoneTypeId": 0,
            "BuildingTypologyId": None,
            "ZoningRegulationName": "Miami 21 Code",
            "ZoningRegulationLink": "https://codehub.gridics.com/us/fl/miami",
            "ZoneCombinationName": "CI",
        }
    )

    assert allowance.ZoneTypeId == "0"
