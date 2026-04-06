"""Application configuration for the UZone backend."""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UZONE_", env_file=".env", extra="ignore")

    app_name: str = "UZone API"
    app_version: str = "0.1.0"
    allowed_origins: str = "http://localhost:3001,http://127.0.0.1:3001"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/uzone"
    auth_provider: str = "local"
    clerk_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("UZONE_CLERK_SECRET_KEY", "CLERK_SECRET_KEY"),
    )
    clerk_pem_public_key: str | None = None
    clerk_jwks_url: str = "https://api.clerk.com/v1/jwks"
    clerk_authorized_parties: str = "http://localhost:3001,http://127.0.0.1:3001"
    gridics_clerk_organization_id: str | None = None
    payment_providers: str = "manual"
    default_payment_provider: str = "manual"
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    email_provider: str = "console"
    email_from: str = "noreply@uzone.local"
    resend_api_key: str | None = None
    postmark_server_token: str | None = None
    aws_region: str | None = None
    artifacts_dir: str = "/tmp/uzone-artifacts"
    assets_bucket: str | None = None
    assets_prefix: str = "jurisdictions"
    cache_backend: str = "local"
    cache_redis_url: str | None = None
    cache_default_ttl_seconds: int = 300
    admin_config_cache_ttl_seconds: int = 120
    tenant_config_ttl_seconds: int = 300
    embed_session_signing_secret: str | None = None
    embed_session_issuer: str = "uzone"
    embed_session_audience: str = "uzone-embed-widget"
    embed_session_ttl_seconds: int = 3600
    enable_agent_os: bool = True
    require_agent_os: bool = False
    zoning_embedder_provider: str = "gemini"
    zoning_embedder_model_id: str = "gemini-embedding-001"
    zoning_embedder_dimensions: int = 1536
    zoning_embedder_api_key: str | None = None
    zoning_embedder_base_url: str | None = None
    zoning_embedder_requests_per_minute: float = 0.0
    zoning_agent_llm_provider: str = "gemini"
    zoning_agent_llm_model_id: str = "gemini-2.0-flash-001"
    zoning_agent_llm_api_key: str | None = None
    zoning_agent_llm_base_url: str | None = None


settings = Settings()
