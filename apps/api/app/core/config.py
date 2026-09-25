"""Application settings, loaded from environment variables (see .env.example)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    # --- core ---
    environment: Literal["development", "test", "production"] = "development"
    app_name: str = "AI Teacher Assistant"
    public_web_url: str = "http://localhost:3000"
    public_api_url: str = "http://localhost:8000"
    secret_key: str = "dev-insecure-change-me-please-0123456789abcdef"
    access_token_minutes: int = 60 * 24 * 7
    cookie_secure: bool = False
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- database / cache ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/teacher_assistant"
    redis_url: str | None = None

    # --- storage ---
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_dir: Path = API_ROOT / "var" / "storage"
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    signed_url_ttl_seconds: int = 900

    # --- uploads ---
    max_upload_mb: int = 100
    max_pages: int = 300
    clamd_host: str | None = None
    clamd_port: int = 3310

    # --- AI providers (server-side only; never exposed to the browser) ---
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None  # any OpenAI-compatible endpoint
    gemini_api_key: str | None = None
    ai_offline_mode: bool = False  # force the deterministic offline provider (tests, demos)

    # Model routing: "<provider>:<model>". Admins can override at runtime (app_settings table).
    model_planning: str = "anthropic:claude-opus-5"
    model_content: str = "anthropic:claude-sonnet-5"
    model_fast: str = "anthropic:claude-haiku-4-5"
    model_vision: str = "anthropic:claude-sonnet-5"
    model_qc: str = "anthropic:claude-haiku-4-5"
    model_embedding: str = "openai:text-embedding-3-small"
    model_image: str = "openai:gpt-image-1-mini"
    embedding_dim: int = 1536
    ai_request_timeout_s: float = 180.0
    ai_max_concurrency: int = 6

    # Optional free stock image search (Openverse, CC-licensed)
    openverse_enabled: bool = True

    # --- billing ---
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_prices: dict[str, str] = Field(default_factory=dict)  # {"teacher_monthly": "price_..."}

    # --- WhatsApp Cloud API ---
    whatsapp_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_app_secret: str | None = None
    whatsapp_verify_token: str = "dev-verify-token"
    whatsapp_graph_version: str = "v21.0"

    # --- email ---
    smtp_url: str | None = None
    email_from: str = "AI Teacher Assistant <no-reply@example.com>"

    # --- OAuth (Google / Microsoft) ---
    google_client_id: str | None = None
    google_client_secret: str | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None

    # --- observability ---
    sentry_dsn: str | None = None
    log_level: str = "INFO"

    # --- rendering / QC ---
    soffice_path: str = "soffice"
    render_timeout_s: int = 180
    min_body_font_pt: float = 16.0
    worker_poll_interval_s: float = 1.0
    run_jobs_inline: bool = False  # tests: execute jobs synchronously

    admin_emails: list[str] = []

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    return Settings()
