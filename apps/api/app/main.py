"""FastAPI application entry point:  uvicorn app.main:app"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import assistant_memory, auth, content, platform, teacher
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, log, request_id_var

logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.1,
                        send_default_pii=False)
    import app.jobs.handlers  # noqa: F401  register job handlers (inline execution)
    import app.services.assistant  # noqa: F401  register offline intent generator
    from app.ai.service import get_ai

    ai = get_ai()
    log(logger, logging.INFO, "startup", ai_mode=ai.mode, providers=ai.live_providers)
    if settings.environment == "production" and settings.secret_key.startswith("dev-insecure"):
        raise RuntimeError("SECRET_KEY must be set in production")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AI Teacher Assistant API", version="1.0.0", lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        start = time.monotonic()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        ms = int((time.monotonic() - start) * 1000)
        response.headers["x-request-id"] = rid
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
        response.headers["x-frame-options"] = "DENY"
        if settings.is_production:
            response.headers["strict-transport-security"] = "max-age=31536000; includeSubDomains"
        if not request.url.path.endswith("/events"):
            log(logger, logging.INFO, "request", method=request.method, path=request.url.path,
                status=response.status_code, ms=ms, request_id=rid)
        return response

    install_error_handlers(app)
    for r in (auth.router, teacher.router, content.router, assistant_memory.router, platform.router):
        app.include_router(r, prefix="/api/v1")
    return app


app = create_app()
