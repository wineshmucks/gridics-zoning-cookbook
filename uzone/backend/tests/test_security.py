"""Unit tests for auth token verification error handling."""

from __future__ import annotations

import httpx
import pytest
from fastapi import HTTPException, status

from app.core import security


@pytest.fixture(autouse=True)
def clear_clerk_public_keys_cache() -> None:
    security._clerk_public_keys.cache_clear()
    yield
    security._clerk_public_keys.cache_clear()


def test_clerk_jwks_unauthorized_raises_service_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("GET", "https://example.com/jwks")
    response = httpx.Response(status_code=401, request=request)

    def fake_get(url: str, timeout: float) -> httpx.Response:
        return response

    monkeypatch.setattr(security.settings, "clerk_pem_public_key", None)
    monkeypatch.setattr(security.settings, "clerk_jwks_url", "https://example.com/jwks")
    monkeypatch.setattr(security.httpx, "get", fake_get)

    with pytest.raises(HTTPException) as exc_info:
        security._clerk_public_keys()

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "rejected the backend request" in exc_info.value.detail


def test_clerk_jwks_network_error_raises_service_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, timeout: float) -> httpx.Response:
        raise httpx.ConnectError("boom", request=httpx.Request("GET", url))

    monkeypatch.setattr(security.settings, "clerk_pem_public_key", None)
    monkeypatch.setattr(security.settings, "clerk_jwks_url", "https://example.com/jwks")
    monkeypatch.setattr(security.httpx, "get", fake_get)

    with pytest.raises(HTTPException) as exc_info:
        security._clerk_public_keys()

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exc_info.value.detail == "Unable to reach Clerk JWKS"
