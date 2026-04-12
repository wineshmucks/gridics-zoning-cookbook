"""Tests for jurisdiction resolver service."""

from __future__ import annotations

import types

from app.services.jurisdiction_resolver import resolve_jurisdiction_for_property_request


def test_resolve_jurisdiction_returns_unresolved_when_lookup_not_ready() -> None:
    tenant = types.SimpleNamespace(city_name="Miami", settings_json={"state": "fl"})
    result = resolve_jurisdiction_for_property_request(
        tenant_client=tenant,
        standardized_address="123 Main Street",
        lookup_ready=False,
    )
    assert result["jurisdiction_status"] == "unresolved"
    assert result["is_ambiguous"] is True
    assert result["clarification_type"] == "address_missing_details"


def test_resolve_jurisdiction_detects_city_mismatch() -> None:
    tenant = types.SimpleNamespace(city_name="Miami", settings_json={"state": "fl"})
    result = resolve_jurisdiction_for_property_request(
        tenant_client=tenant,
        standardized_address="123 Main Street, Orlando, FL 32801",
        lookup_ready=True,
        resolved_city="Orlando",
        resolved_state="FL",
    )
    assert result["jurisdiction_status"] == "out_of_jurisdiction"
    assert result["clarification_type"] == "jurisdiction_mismatch"
