"""Request pipeline shared by every API call.

In order: request id -> CSRF origin check -> maintenance mode -> global rate limits -> idempotency replay ->
the route -> security headers -> one metadata row in api_requests (never request or response bodies).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import secrets
import time
import uuid
from typing import Any
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.core.db import get_sessionmaker, utcnow, uuid7
from app.core.errors import error_response
from app.core.logging import log, request_id_var
from app.core.ratelimit import limiter
from app.core.request_meta import client_ip
from app.core.security import COOKIE_NAME, decode_token

logger = logging.getLogger("api")

API = "/api/v1"
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{8,64}$")
IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9_\-:.]{8,100}$")
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
NO_LIMIT = (f"{API}/health", f"{API}/ready", f"{API}/webhooks/")
MAINTENANCE_OPEN = (f"{API}/health", f"{API}/ready", f"{API}/public/", f"{API}/auth/", f"{API}/admin/",
                    f"{API}/webhooks/", f"{API}/legal", f"{API}/status")
# Endpoints that start paid AI work get their own, tighter per-user bucket.
AI_ROUTES = re.compile(rf"^{API}/(courses(/[^/]+/(generate|replan))?|lessons/[^/]+/(regenerate|slides/\d+/regenerate)"
                       rf"|documents|media|assistant/(chat|tasks)|planner/.+)$")
PRIVATE_PREFIXES = (f"{API}/auth", f"{API}/me", f"{API}/admin", f"{API}/billing", f"{API}/support")
ID_SEGMENT = re.compile(r"/(?:[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|\d+|req_\w+)"
                        r"(?=/|$)")
MAX_IDEMPOTENT_BODY = 256 * 1024


def new_request_id() -> str:
    return "req_" + secrets.token_hex(10)


def _token_claims(request: Request) -> dict[str, Any] | None:
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else request.cookies.get(COOKIE_NAME)
    return decode_token(token) if token else None


def route_template(request: Request) -> str:
    """The matched route's template (/api/v1/lessons/{lesson_id}), so logs group by endpoint, not by id.
    Set by capture_route during routing; unmatched paths fall back to the path with ids masked."""
    cached = getattr(request.state, "route_template", None)
    return (cached or ID_SEGMENT.sub("/{id}", request.url.path))[:200]


async def capture_route(request: Request) -> None:
    """App-wide dependency: remember which route matched (request.state is shared with the middleware)."""
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path:
        # Routers are included under /api/v1; newer FastAPI keeps the route's own path relative to that prefix.
        request.state.route_template = path if path.startswith(API) else API + path


# --------------------------------------------------------------------------- request log


class ApiRequestLog:
    """Buffers request metadata and writes it in batches, so logging never adds a DB round trip to a request."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self._task: asyncio.Task | None = None

    def add(self, row: dict[str, Any]) -> None:
        self.rows.append(row)
        if len(self.rows) >= 200:
            asyncio.get_running_loop().create_task(self.flush())
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self._periodic())

    async def _periodic(self) -> None:
        while self.rows:
            await asyncio.sleep(2)
            await self.flush()

    async def flush(self) -> int:
        rows, self.rows = self.rows, []
        if not rows:
            return 0
        try:
            from app.models import ApiRequest

            async with get_sessionmaker()() as s:
                await s.execute(insert(ApiRequest).on_conflict_do_nothing(index_elements=["request_id"]), rows)
                await s.commit()
        except Exception as e:  # noqa: BLE001 - the request log must never break requests
            log(logger, logging.WARNING, "api_log_flush_failed", error=str(e)[:200], dropped=len(rows))
            return 0
        return len(rows)


api_log = ApiRequestLog()


# --------------------------------------------------------------------------- helpers


async def _security_event(type_: str, request: Request, *, throttle_key: str, user_id: str | None = None,
                          **details: Any) -> None:
    """Record at most one event per key per minute, so a flood doesn't become a flood of events."""
    if not await limiter.hit(f"sev:{type_}:{throttle_key}", 1, 1 / 60):
        return
    try:
        from app.services.events import security_event

        async with get_sessionmaker()() as s:
            security_event(s, type_, request=request, user_id=uuid.UUID(user_id) if user_id else None, **details)
            await s.commit()
    except Exception as e:  # noqa: BLE001
        log(logger, logging.WARNING, "security_event_failed", error=str(e)[:200])


def _allowed_origins() -> set[str]:
    s = get_settings()
    out = set()
    for o in [s.public_web_url, *s.cors_origins]:
        u = urlparse(o)
        if u.scheme and u.netloc:
            out.add(f"{u.scheme}://{u.netloc}")
    return out


def _csrf_rejected(request: Request) -> bool:
    """Cookie-authenticated writes must come from our own site. Bearer-token clients aren't exposed to CSRF."""
    if request.method not in UNSAFE or request.url.path.startswith(f"{API}/webhooks/"):
        return False
    if request.headers.get("authorization", "").lower().startswith("bearer ") or COOKIE_NAME not in request.cookies:
        return False
    origin = request.headers.get("origin")
    if not origin and request.headers.get("referer"):
        u = urlparse(request.headers["referer"])
        origin = f"{u.scheme}://{u.netloc}"
    if origin:
        return origin not in _allowed_origins()
    return request.headers.get("sec-fetch-site") == "cross-site"


async def _is_staff(user_id: str | None) -> bool:
    if not user_id:
        return False
    from app.models import User

    async with get_sessionmaker()() as s:
        role = (await s.execute(select(User.role).where(User.id == uuid.UUID(user_id)))).scalar_one_or_none()
    return role == "admin"


async def _guard(request: Request, claims: dict | None) -> Response | None:
    from app.services.settings import get_setting_cached

    path = request.url.path
    uid = claims.get("sub") if claims else None

    if _csrf_rejected(request):
        await _security_event("suspicious_request", request, throttle_key=client_ip(request) or "?", user_id=uid,
                              reason="csrf_origin", origin=request.headers.get("origin"))
        return error_response(403, "csrf_failed", "This request didn't come from Clastio. Reload the page and "
                              "try again.")

    # Probes must still work when the database or cache is unavailable.
    if path in (f"{API}/health", f"{API}/ready"):
        return None

    system = await get_setting_cached("system")
    maintenance = (system or {}).get("maintenance") or {}
    if maintenance.get("enabled") and not path.startswith(MAINTENANCE_OPEN) and not await _is_staff(uid):
        return error_response(503, "maintenance", maintenance.get("message") or "Clastio is down for scheduled "
                              "maintenance. Please try again shortly.", {"until": maintenance.get("until")},
                              headers={"Retry-After": "300"})

    if path.startswith(NO_LIMIT):
        return None
    limits = await get_setting_cached("rate_limits")
    ip = client_ip(request) or "unknown"
    checks = [(f"g:ip:{ip}", int(limits.get("ip_per_minute", 300)), "ip")]
    if uid:
        checks.append((f"g:user:{uid}", int(limits.get("user_per_minute", 240)), "user"))
        if request.method == "POST" and AI_ROUTES.match(path):
            checks.append((f"g:ai:{uid}", int(limits.get("ai_per_minute", 20)), "ai"))
    shown: tuple[int, int] | None = None
    for key, per_minute, scope in checks:
        ok, left = await limiter.take(key, per_minute, per_minute / 60)
        if not ok:
            await _security_event("rate_limited", request, throttle_key=key, user_id=uid, scope=scope,
                                  route=route_template(request))
            retry = max(1, int(60 / per_minute) + 1)
            return error_response(429, "rate_limited", "Too many requests. Please slow down and try again in a "
                                  "moment.", {"scope": scope},
                                  headers={"Retry-After": str(retry), "X-RateLimit-Limit": str(per_minute),
                                           "X-RateLimit-Remaining": "0"})
        if shown is None or left < shown[1]:
            shown = (per_minute, left)
    request.state.rate_limit = shown
    return None


# --------------------------------------------------------------------------- idempotency


async def _idempotent(request: Request, call_next, user_id: str) -> Response:
    """Replay the stored response for a repeated Idempotency-Key, so a retried "generate" or "checkout" never
    charges twice. Keys are scoped to the user and kept for 24 hours."""
    from app.models import IdempotencyKey

    key = request.headers["idempotency-key"].strip()
    if not IDEMPOTENCY_KEY_RE.match(key):
        return error_response(400, "invalid_idempotency_key", "Idempotency-Key must be 8-100 letters, digits or "
                              "- _ : . characters.")
    body = await request.body()
    digest = hashlib.sha256(request.method.encode() + request.url.path.encode() + b"\n" + body).hexdigest()
    uid = uuid.UUID(user_id)
    async with get_sessionmaker()() as s:
        res = await s.execute(insert(IdempotencyKey).values(
            id=uuid7(), user_id=uid, key=key, route=request.url.path[:200], request_hash=digest, status="processing",
            created_at=utcnow()).on_conflict_do_nothing(index_elements=["user_id", "key"]))
        await s.commit()
        if not res.rowcount:
            row = (await s.execute(select(IdempotencyKey).where(IdempotencyKey.user_id == uid,
                                                                IdempotencyKey.key == key))).scalars().one()
            if row.request_hash != digest:
                return error_response(422, "idempotency_key_reused", "This Idempotency-Key was already used for a "
                                      "different request.")
            if row.status != "done":
                return error_response(409, "request_in_progress", "The same request is still being processed.",
                                      headers={"Retry-After": "2"})
            return JSONResponse(row.response_body, status_code=row.response_status or 200,
                                headers={"Idempotent-Replayed": "true"})
    try:
        response = await call_next(request)
    except Exception:
        await _forget_key(uid, key)
        raise
    ctype = response.headers.get("content-type", "")
    if not 200 <= response.status_code < 300 or not ctype.startswith("application/json"):
        await _forget_key(uid, key)  # failures and streams can be retried with the same key
        return response
    chunks = [c async for c in response.body_iterator]  # type: ignore[attr-defined]
    raw = b"".join(chunks)
    headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
    if len(raw) <= MAX_IDEMPOTENT_BODY:
        async with get_sessionmaker()() as s:
            row = (await s.execute(select(IdempotencyKey).where(IdempotencyKey.user_id == uid,
                                                                IdempotencyKey.key == key))).scalars().one()
            row.status, row.response_status, row.response_body = "done", response.status_code, json.loads(raw)
            await s.commit()
    else:
        await _forget_key(uid, key)
    return Response(content=raw, status_code=response.status_code, headers=headers)


async def _forget_key(user_id: uuid.UUID, key: str) -> None:
    from app.models import IdempotencyKey

    async with get_sessionmaker()() as s:
        await s.execute(delete(IdempotencyKey).where(IdempotencyKey.user_id == user_id, IdempotencyKey.key == key))
        await s.commit()


# --------------------------------------------------------------------------- the middleware


def _security_headers(request: Request, response: Response) -> None:
    s = get_settings()
    h = response.headers
    h["X-Content-Type-Options"] = "nosniff"
    h["Referrer-Policy"] = "strict-origin-when-cross-origin"
    h["X-Frame-Options"] = "DENY"
    h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if not request.url.path.startswith(f"{API}/docs"):
        h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    if s.is_production:
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if (request.url.path.startswith(PRIVATE_PREFIXES)
            or request.headers.get("authorization") or request.cookies.get(COOKIE_NAME)):
        h.setdefault("Cache-Control", "no-store")


async def platform_middleware(request: Request, call_next):
    incoming = request.headers.get("x-request-id", "")
    rid = incoming if REQUEST_ID_RE.match(incoming) else new_request_id()
    token = request_id_var.set(rid)
    request.state.request_id = rid
    start = time.monotonic()
    path = request.url.path
    claims = _token_claims(request) if path.startswith("/api/") else None
    status = 500
    try:
        response = await _guard(request, claims) if path.startswith(API) else None
        if response is None:
            uid = claims.get("sub") if claims else None
            if request.method == "POST" and uid and request.headers.get("idempotency-key"):
                response = await _idempotent(request, call_next, uid)
            else:
                response = await call_next(request)
    except Exception as exc:  # noqa: BLE001 - last line of defence: a generic 500 with the request id, no internals
        request.state.error_code = "internal_error"
        log(logger, logging.ERROR, "unhandled_error", exc_info=True, error_type=type(exc).__name__,
            route=route_template(request))
        if get_settings().sentry_dsn:
            import sentry_sdk

            sentry_sdk.capture_exception(exc)
        response = error_response(500, "internal_error", "Something went wrong on our side. Please try again; if "
                                  "it keeps happening, contact support with the request ID.")
    try:
        status = response.status_code
        response.headers["X-Request-ID"] = rid
        rate = getattr(request.state, "rate_limit", None)
        if rate:
            response.headers["X-RateLimit-Limit"] = str(rate[0])
            response.headers["X-RateLimit-Remaining"] = str(rate[1])
        _security_headers(request, response)
        if status in (401, 403) and path.startswith(API):
            ip = client_ip(request) or "?"
            if not await limiter.hit(f"authfail:{ip}", 40, 40 / 600):
                await _security_event("suspicious_request", request, throttle_key=ip, reason="many_auth_failures",
                                      route=route_template(request))
        return response
    finally:
        ms = int((time.monotonic() - start) * 1000)
        if path.startswith(API) and not path.startswith((f"{API}/health", f"{API}/ready")):
            if not path.endswith("/events"):
                log(logger, logging.INFO, "request", method=request.method, route=route_template(request),
                    status=status, ms=ms)
            if get_settings().api_request_log:
                uid = getattr(request.state, "user_id", None) or (claims.get("sub") if claims else None)
                api_log.add({"id": uuid7(), "request_id": rid, "user_id": uuid.UUID(str(uid)) if uid else None,
                             "method": request.method[:8], "route": route_template(request), "status": status,
                             "duration_ms": ms, "error_code": getattr(request.state, "error_code", None),
                             "ip": client_ip(request), "user_agent": (request.headers.get("user-agent") or "")[:300],
                             "created_at": utcnow()})
        request_id_var.reset(token)
