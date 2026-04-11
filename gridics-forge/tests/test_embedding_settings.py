from zoning_agno.config.settings import Settings


def test_settings_use_embedding_env_vars(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openrouter")
    monkeypatch.setenv("EMBEDDING_MODEL", "nvidia/llama-nemotron-embed-vl-1b-v2:free")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "2048")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")

    settings = Settings()

    assert settings.embedding_provider == "openrouter"
    assert settings.embedding_model == "nvidia/llama-nemotron-embed-vl-1b-v2:free"
    assert settings.embedding_dimensions == 2048
    assert settings.embedding_api_key == "test-key"
