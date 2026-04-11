"""Tests for constructor compatibility helpers."""

from __future__ import annotations

from app.services.compat import build_with_supported_kwargs


def test_build_with_supported_kwargs_filters_unknown_kwargs() -> None:
    captured = {}

    class FakeType:
        def __init__(self, *, name=None):
            captured["name"] = name

    instance = build_with_supported_kwargs(FakeType, id="ignored", name="kept")

    assert isinstance(instance, FakeType)
    assert captured == {"name": "kept"}
