"""Tests for embed session utilities."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core import config
from app.services import embed_service


@pytest.fixture(autouse=True)
def clear_embed_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.settings, "embed_session_signing_secret", "test-secret-0123456789abcdef0123456789")
    monkeypatch.setattr(config.settings, "embed_session_issuer", "uzone")
    monkeypatch.setattr(config.settings, "embed_session_audience", "uzone-embed-widget")
    monkeypatch.setattr(config.settings, "embed_session_ttl_seconds", 3600)


def test_embed_secret_hash_verification_round_trip() -> None:
    secret = embed_service.generate_embed_secret()
    secret_hash = embed_service.hash_embed_secret(secret)

    assert embed_service.verify_embed_secret(secret, secret_hash) is True
    assert embed_service.verify_embed_secret(f"{secret}-wrong", secret_hash) is False


def test_embed_session_token_round_trip() -> None:
    tenant_client = SimpleNamespace(
        client_id="dream-town",
        city_name="Dream Town",
        department_name="Planning",
        settings_json={"market": "Miami, FL"},
    )

    token, expires_at = embed_service.issue_embed_session_token(
        tenant_client=tenant_client,
        embed_origin="https://example.com",
        assistant_disclaimer_text="Use official sources.",
        widget_title="Ask Dream Town",
        launcher_label="Have a question?",
        accent_color="#123456",
        market="Miami, FL",
    )
    payload = embed_service.decode_embed_session_token(token)

    assert payload["client_id"] == "dream-town"
    assert payload["origin"] == "https://example.com"
    assert payload["assistant_disclaimer_text"] == "Use official sources."
    assert payload["widget_title"] == "Ask Dream Town"
    assert payload["launcher_label"] == "Have a question?"
    assert payload["accent_color"] == "#123456"
    assert payload["market"] == "Miami, FL"
    assert payload["exp"] == int(expires_at.timestamp())
