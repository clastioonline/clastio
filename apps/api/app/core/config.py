"""Application settings, loaded from environment variables (see .env.example)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # env_ignore_empty: a blank line such as "SECRET_KEY=" copied from .env.example means "use the default".
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore", env_ignore_empty=True)

    # --- core ---
    environment: Literal["development", "test", "production"] = "development"
    app_name: str = "Clastio"
    # Build identifier shown in /health, logs and error reports (set by CI, e.g. the git SHA or a release tag).
    app_version: str = "dev"
    # The one origin browsers use. The web app proxies /api to the API, so OAuth callbacks and cookies live here too.
    public_web_url: str = "http://localhost:3000"
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
    model_video: str = "openai:sora-2"
    embedding_dim: int = 1536
    ai_request_timeout_s: float = 180.0
    ai_max_concurrency: int = 6

    # Optional free stock image search (Openverse, CC-licensed)
    openverse_enabled: bool = True

    # --- billing ---
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_prices: dict[str, str] = Field(default_factory=dict)  # {"teacher_monthly": "price_..."}

    # Dodo Payments (merchant of record: handles VAT/GST, cards, UPI and local methods in the UAE and India)
    dodo_payments_api_key: str | None = None
    dodo_payments_webhook_key: str | None = None
    dodo_payments_environment: Literal["test_mode", "live_mode"] = "test_mode"
    dodo_products: dict[str, str] = Field(default_factory=dict)  # {"teacher_month": "pdt_...", ...}

    # --- WhatsApp Cloud API ---
    whatsapp_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_app_secret: str | None = None
    whatsapp_verify_token: str = "dev-verify-token"
    whatsapp_graph_version: str = "v21.0"

    # --- email ---
    smtp_url: str | None = None
    email_from: str = "Clastio <no-reply@example.com>"

    # --- bot protection (Cloudflare Turnstile); both empty = off ---
    turnstile_site_key: str | None = None
    turnstile_secret: str | None = None

    # --- OAuth (Google / Microsoft) ---
    google_client_id: str | None = None
    google_client_secret: str | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None

    # --- observability ---
    sentry_dsn: str | None = None
    log_level: str = "INFO"
    # Record one metadata row per API request (never bodies) for the admin usage dashboard and request trace.
    api_request_log: bool = True

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

    def validate_production(self) -> None:
        """Fail before serving requests or processing jobs with unsafe deployment settings."""
        if not self.is_production:
            return
        errors = []
        if self.secret_key.startswith("dev-insecure") or len(self.secret_key) < 32:
            errors.append("SECRET_KEY must be a random value of at least 32 characters")
        if not self.cookie_secure:
            errors.append("COOKIE_SECURE must be true")
        url = urlparse(self.public_web_url)
        if url.scheme != "https" or not url.hostname or url.hostname in {"localhost", "127.0.0.1", "::1"}:
            errors.append("PUBLIC_WEB_URL must be your public HTTPS origin")
        if url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
            errors.append("PUBLIC_WEB_URL must contain only an origin")
        if self.run_jobs_inline:
            errors.append("RUN_JOBS_INLINE must be false; run a separate worker")
        if errors:
            raise RuntimeError("Invalid production configuration: " + "; ".join(errors))

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    return Settings()
