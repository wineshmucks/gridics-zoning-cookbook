"""Application configuration for the UZone backend."""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UZONE_", env_file=".env", extra="ignore")

    app_name: str = "Gridics UZone API"
    app_version: str = "0.1.0"
    allowed_origins: str = (
        "http://localhost:3001,"
        "http://127.0.0.1:3001,"
        "http://st1-agentic.gridics.local:3001,"
        "http://st1-zvl.gridics.local:3001,"
        "http://st1-agentic.gridics.test:3001,"
        "http://st1-zvl.gridics.test:3001"
    )
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/uzone"
    auth_provider: str = "local"
    clerk_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("UZONE_CLERK_SECRET_KEY", "CLERK_SECRET_KEY"),
    )
    clerk_pem_public_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("UZONE_CLERK_PEM_PUBLIC_KEY", "CLERK_PEM_PUBLIC_KEY"),
    )
    clerk_jwks_url: str = Field(
        default="https://api.clerk.com/v1/jwks",
        validation_alias=AliasChoices("UZONE_CLERK_JWKS_URL", "CLERK_JWKS_URL"),
    )
    clerk_authorized_parties: str = Field(
        default=(
        "http://localhost:3001,"
        "http://127.0.0.1:3001,"
        "http://st1-agentic.gridics.local:3001,"
        "http://st1-zvl.gridics.local:3001,"
        "http://st1-agentic.gridics.test:3001,"
        "http://st1-zvl.gridics.test:3001"
        ),
        validation_alias=AliasChoices("UZONE_CLERK_AUTHORIZED_PARTIES", "CLERK_AUTHORIZED_PARTIES"),
    )
    gridics_clerk_organization_id: str | None = None
    payment_providers: str = "manual"
    default_payment_provider: str = "manual"
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    email_provider: str = "console"
    email_from: str = "noreply@uzone.local"
    resend_api_key: str | None = None
    postmark_server_token: str | None = None
    mandrill_api_key: str | None = None
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
    zoning_embedder_api_key: str | None = None
    zoning_embedder_requests_per_minute: float = 0.0
    zoning_agent_llm_model_id: str = "gemini-2.0-flash-001"
    zoning_agent_llm_api_key: str | None = None
    agno_session_table: str = Field(
        default="aos_sessions",
        validation_alias=AliasChoices("AGNO_SESSION_TABLE", "UZONE_AGNO_SESSION_TABLE"),
    )
    agno_store_history_messages: bool = Field(
        default=False,
        validation_alias=AliasChoices("AGNO_STORE_HISTORY_MESSAGES", "UZONE_AGNO_STORE_HISTORY_MESSAGES"),
    )
    agno_num_history_runs: int = Field(
        default=5,
        validation_alias=AliasChoices("AGNO_NUM_HISTORY_RUNS", "UZONE_AGNO_NUM_HISTORY_RUNS"),
    )


settings = Settings()
