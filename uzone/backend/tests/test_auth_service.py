"""Unit tests for authentication helpers."""

from app.services.auth_service import (
    hash_password,
    hash_session_token,
    new_session_token,
    session_expiry,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    encoded = hash_password("correct horse battery staple")
    assert encoded != "correct horse battery staple"
    assert verify_password("correct horse battery staple", encoded) is True
    assert verify_password("wrong password", encoded) is False


def test_new_session_token_is_not_empty() -> None:
    token = new_session_token()
    assert token
    assert hash_session_token(token)


def test_session_expiry_is_in_the_future() -> None:
    expires_at = session_expiry()
    assert expires_at.tzinfo is not None

