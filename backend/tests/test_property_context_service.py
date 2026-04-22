from __future__ import annotations

from app.services.agentic.property_context_service import GridicsPropertyContextService


class DummyGridicsAdapter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_property_record_by_coordinates(
        self,
        *,
        latitude: float,
        longitude: float,
        state_env: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "kind": "coordinates",
                "latitude": latitude,
                "longitude": longitude,
                "state_env": state_env,
            }
        )
        if state_env is None:
            raise RuntimeError('Gridics HTTP 400: {"status":"ERROR","message":"\\"state_env\\" is required"}')
        return {
            "data": [
                {
                    "Address": "3148 Mary Street",
                    "City": "Miami",
                    "State": "FL",
                    "ZipCode": "33133",
                    "FolioNumber": "01-2345-678-9000",
                    "Buildings": [
                        {
                            "ZoningAllowance": {"ZoneCombinationName": "T3-O"},
                            "Envelope": {
                                "LotAreaFeet": 5000,
                                "LotAreaAcres": 0.1148,
                                "DensityUnits": 1,
                                "TotalBuidingHeight": 2,
                                "TotalBuildingHeightFeet": 35,
                                "FloorAreaRatio": 0.9,
                                "EffectivePFrontSetbackPrincipal": 20,
                                "EffectivePSideSetback": 5,
                                "EffectivePRearSetback": 10,
                            },
                            "Overlays": [{"Name": "NCD-2"}],
                            "Uses": [
                                {
                                    "TypeName": "Residential",
                                    "CalibrationUsesLabel": "Single-family",
                                    "AllowedUsesName": "Allowed",
                                }
                            ],
                        }
                    ],
                }
            ]
        }

    def get_property_record(self, *, state_code: str, address: str, zip_code: str) -> dict[str, object]:
        self.calls.append(
            {
                "kind": "address",
                "state_code": state_code,
                "address": address,
                "zip_code": zip_code,
            }
        )
        return {
            "data": [
                {
                    "Address": "3148 Mary Street",
                    "City": "Miami",
                    "State": "FL",
                    "ZipCode": "33133",
                    "FolioNumber": "01-2345-678-9000",
                    "Buildings": [
                        {
                            "ZoningAllowance": {"ZoneCombinationName": "T3-O"},
                            "Envelope": {
                                "LotAreaFeet": 5000,
                                "LotAreaAcres": 0.1148,
                                "DensityUnits": 1,
                                "TotalBuidingHeight": 2,
                                "TotalBuildingHeightFeet": 35,
                                "FloorAreaRatio": 0.9,
                                "EffectivePFrontSetbackPrincipal": 20,
                                "EffectivePSideSetback": 5,
                                "EffectivePRearSetback": 10,
                            },
                            "Overlays": [{"Name": "NCD-2"}],
                            "Uses": [
                                {
                                    "TypeName": "Residential",
                                    "CalibrationUsesLabel": "Single-family",
                                    "AllowedUsesName": "Allowed",
                                }
                            ],
                        }
                    ],
                }
            ]
        }


def test_property_context_falls_back_to_address_lookup_when_gridics_requires_state_env() -> None:
    adapter = DummyGridicsAdapter()
    service = GridicsPropertyContextService(adapter=adapter)

    result = service.get_property_context(
        lat=25.732787,
        lng=-80.239989,
        state_env="fl",
        jurisdiction_id="org_3AhfzeTJJvPg6OvNf8KS1pf2m4N",
        jurisdiction_name="City of Miami2",
        address="3148 Mary Street, Miami, Florida 33133, United States",
    )

    assert result.status == "success"
    assert result.jurisdiction_name == "City of Miami2"
    assert result.zoning_district == "T3-O"
    assert result.allowed_uses == ["Single-family"]
    assert adapter.calls == [
        {"kind": "coordinates", "latitude": 25.732787, "longitude": -80.239989, "state_env": "fl"}
    ]
