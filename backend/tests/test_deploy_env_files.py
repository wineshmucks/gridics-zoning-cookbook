"""Guardrails for deploy env files that feed staging and production."""

from __future__ import annotations

from pathlib import Path


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def test_deploy_env_files_use_gemini_embedder_settings() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    env_files = [repo_root / ".env-deploy.staging", repo_root / ".env-deploy.prod"]

    for env_file in env_files:
        values = _read_env_file(env_file)
        assert values["UZONE_ZONING_EMBEDDER_PROVIDER"] == "gemini"
        assert values["UZONE_ZONING_EMBEDDER_MODEL_ID"] == "gemini-embedding-001"
        assert values["UZONE_ZONING_EMBEDDER_DIMENSIONS"] == "1536"
