"""Tests for release gate script logic."""

from __future__ import annotations

from pathlib import Path

from app.scripts import check_assistant_release_gate as gate


def test_release_gate_passes_when_thresholds_met(monkeypatch) -> None:
    monkeypatch.setattr(
        gate,
        "_load_cases",
        lambda filename: [
            {
                "id": "c1",
                "query": "What are setbacks?",
                "question_type": "general_zoning",
                "tenant": {"city_name": "Miami", "settings_json": {"state": "fl"}},
                "expected_policy_decision": "allow",
            }
        ],
    )
    assert gate.main() == 0


def test_release_gate_passes_with_repository_eval_fixtures(monkeypatch) -> None:
    backend_root = Path(gate.__file__).resolve().parents[2]
    monkeypatch.setattr(gate, "BACKEND_ROOT", backend_root)
    assert gate.main() == 0
