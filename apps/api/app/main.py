"""FastAPI application entry point:  uvicorn app.main:app"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import account, admin, assistant_memory, auth, content, media, platform, teacher
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.http import capture_route, platform_middleware
from app.core.logging import configure_logging, log, redact_sentry_event

logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.validate_production()
    configure_logging(settings.log_level, environment=settings.environment, version=settings.app_version)
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.1,
                        send_default_pii=False, max_request_body_size="never", include_local_variables=False,
                        before_send=redact_sentry_event, before_send_transaction=redact_sentry_event,
                        release=settings.app_version)
    import app.jobs.handlers  # noqa: F401  register job handlers (inline execution)
    import app.services.assistant  # noqa: F401  register offline intent generator
    from app.ai.service import get_ai

    ai = get_ai()
    log(logger, logging.INFO, "startup", ai_mode=ai.mode, providers=ai.live_providers)
    yield
    from app.core.http import api_log

    await api_log.flush()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Clastio API", version=f"1.0.0+{settings.app_version}", lifespan=lifespan,
                  dependencies=[Depends(capture_route)],
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                       allow_headers=["authorization", "content-type", "idempotency-key", "x-request-id"],
                       expose_headers=["x-request-id", "x-ratelimit-limit", "x-ratelimit-remaining", "retry-after"])

    app.middleware("http")(platform_middleware)

    install_error_handlers(app)
    for r in (auth.router, account.router, admin.router, teacher.router, content.router, assistant_memory.router, media.router, platform.router):
        app.include_router(r, prefix="/api/v1")
    return app


app = create_app()
