"""Request pipeline and cost controls: error envelope, request ids, request log, rate limits, maintenance, CSRF,
idempotency, credit reservations, daily limits, kill switch, upload caps, circuit breaker, health endpoints."""

from __future__ import annotations

import asyncio
import contextlib
import io
import uuid

import httpx
import pytest
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.core.errors import LimitExceeded
from app.models import ApiRequest, GenerationJob, SupportTicket, User
from tests.conftest import make_staff, make_user


@contextlib.asynccontextmanager
async def setting(key: str, value):
    """Temporarily store an admin setting, restoring the previous stored value afterwards."""
    from app.models import AppSetting
    from app.services import settings as settings_svc

    async with get_sessionmaker()() as db:
        row = await db.get(AppSetting, key)
        previous = row.value if row else None
    await settings_svc.set_setting(key, value)
    try:
        yield
    finally:
        if previous is None:
            async with get_sessionmaker()() as db:
                row = await db.get(AppSetting, key)
                if row:
                    await db.delete(row)
                    await db.commit()
            settings_svc._cache.pop(key, None)
        else:
            await settings_svc.set_setting(key, previous)


# --------------------------------------------------------------------------- errors & request ids


async def test_error_envelope_and_request_id(client):
    r = await client.get("/api/v1/projects")
    body = r.json()
    assert r.status_code == 401 and body["success"] is False
    assert set(body["error"]) == {"code", "message", "details", "requestId"}
    assert body["error"]["requestId"] == r.headers["x-request-id"] and r.headers["x-request-id"].startswith("req_")
    r = await client.get("/api/v1/health", headers={"x-request-id": "req_client_supplied_1"})
    assert r.headers["x-request-id"] == "req_client_supplied_1"
    r = await client.get("/api/v1/health", headers={"x-request-id": "bad id with spaces"})
    assert r.headers["x-request-id"].startswith("req_")


async def test_unexpected_errors_hide_internals(app, seeded, monkeypatch):
    from app.services import usage

    async def boom(*a, **k):
        raise RuntimeError("password=hunter2 at postgres://internal-host:5432")

    u_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                 base_url="http://test")
    async with u_client as c:
        u = await make_user(c)
        monkeypatch.setattr(usage, "summary", boom)
        r = await c.get("/api/v1/me/usage", headers=u["headers"])
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error" and r.json()["error"]["requestId"]
    assert "hunter2" not in r.text and "postgres" not in r.text and "Traceback" not in r.text


async def test_validation_errors_do_not_echo_input(client):
    r = await client.post("/api/v1/auth/login", json={"email": "not-an-email", "password": "<script>x</script>"})
    assert r.status_code == 422 and "<script>" not in r.text


async def test_security_headers(client):
    r = await client.get("/api/v1/auth/me")
    for h in ("x-content-type-options", "x-frame-options", "referrer-policy", "content-security-policy"):
        assert h in r.headers
    assert r.headers["cache-control"] == "no-store"


# --------------------------------------------------------------------------- request log


async def test_requests_are_logged_with_route_templates(client):
    from app.core.http import api_log

    u = await make_user(client)
    await client.get(f"/api/v1/courses/{uuid.uuid4()}/progress", headers={**u["headers"], "x-request-id": "req_logtest_0001"})
    await api_log.flush()
    async with get_sessionmaker()() as db:
        row = (await db.execute(select(ApiRequest).where(ApiRequest.request_id == "req_logtest_0001"))).scalars().one()
    assert row.route == "/api/v1/courses/{course_id}/progress" and row.status == 404
    assert row.user_id == uuid.UUID(u["id"]) and row.error_code == "not_found" and row.duration_ms >= 0


async def test_admin_api_usage_dashboard(client):
    from app.core.http import api_log

    analyst = await make_staff(client, "analyst")
    for _ in range(3):
        await client.get("/api/v1/health")
        await client.get("/api/v1/me/usage", headers=analyst["headers"])
    await api_log.flush()
    d = (await client.get("/api/v1/admin/api-usage?days=1&route=/api/v1/me/usage",
                          headers=analyst["headers"])).json()
    assert d["totals"]["requests"] >= 3 and d["totals"]["p95_ms"] is not None
    assert [r["route"] for r in d["by_route"]] == ["/api/v1/me/usage"]
    assert any(u["user_id"] == analyst["id"] for u in d["by_user"])
    assert "by_model" in d["ai"] and "top_spenders" in d["ai"]
    support = await make_staff(client, "support")
    assert (await client.get("/api/v1/admin/api-usage", headers=support["headers"])).status_code == 403


# --------------------------------------------------------------------------- rate limits


async def test_user_rate_limit_headers_and_429(client):
    u = await make_user(client)
    async with setting("rate_limits", {"ip_per_minute": 1000, "user_per_minute": 3, "auth_per_minute": 10,
                                       "ai_per_minute": 20}):
        codes = []
        for _ in range(5):
            r = await client.get("/api/v1/me/usage", headers=u["headers"])
            codes.append(r.status_code)
            if r.status_code == 200:
                assert r.headers["x-ratelimit-limit"] == "3"
                assert int(r.headers["x-ratelimit-remaining"]) >= 0
        assert codes[:3] == [200, 200, 200] and codes[-1] == 429
        assert r.json()["error"]["code"] == "rate_limited" and int(r.headers["retry-after"]) >= 1
        other = await make_user(client)  # limits are per user, not global
        assert (await client.get("/api/v1/me/usage", headers=other["headers"])).status_code == 200
    from app.models import SecurityEvent

    async with get_sessionmaker()() as db:
        ev = (await db.execute(select(SecurityEvent).where(SecurityEvent.type == "rate_limited",
                                                           SecurityEvent.user_id == uuid.UUID(u["id"])))).scalars().all()
    assert len(ev) == 1  # one event per minute, not one per rejected request


# --------------------------------------------------------------------------- maintenance & kill switch


async def test_maintenance_mode_blocks_teachers_not_staff(client):
    u = await make_user(client)
    staff = await make_staff(client, "admin")
    async with setting("system", {"maintenance": {"enabled": True, "message": "Upgrading", "until": None}}):
        r = await client.get("/api/v1/projects", headers=u["headers"])
        assert r.status_code == 503 and r.json()["error"]["code"] == "maintenance"
        assert r.json()["error"]["message"] == "Upgrading" and r.headers["retry-after"]
        assert (await client.get("/api/v1/auth/me", headers=u["headers"])).status_code == 200
        assert (await client.get("/api/v1/projects", headers=staff["headers"])).status_code == 200
        assert (await client.get("/api/v1/health")).status_code == 200
        assert (await client.get("/api/v1/status")).json()["status"] == "maintenance"
    assert (await client.get("/api/v1/projects", headers=u["headers"])).status_code == 200


async def test_ai_kill_switch(client):
    u = await make_user(client)
    async with setting("system", {"ai_generation_enabled": False}):
        r = await client.post("/api/v1/documents", headers=u["headers"],
                              json={"kind": "worksheet", "topic": "Fractions", "grade": "5"})
        assert r.status_code == 503 and r.json()["error"]["code"] == "ai_paused"


async def test_registration_can_be_closed(client):
    async with setting("system", {"registration_enabled": False}):
        r = await client.post("/api/v1/auth/signup", json={"email": f"x-{uuid.uuid4().hex[:6]}@example.com",
                                                            "password": "correct-horse-1", "name": "X",
                                                            "accept_terms": True})
        assert r.status_code == 403 and r.json()["error"]["code"] == "registration_closed"


# --------------------------------------------------------------------------- CSRF


async def test_cookie_writes_require_our_origin(client):
    email = f"c-{uuid.uuid4().hex[:6]}@example.com"
    r = await client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-1", "name": "C",
                                                        "accept_terms": True})
    assert "ata_session" in client.cookies
    body = {"kind": "support", "subject": "Help please", "body": "Something is wrong here."}
    r = await client.post("/api/v1/support/tickets", json=body, headers={"origin": "https://evil.example"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed"
    r = await client.post("/api/v1/support/tickets", json=body, headers={"origin": "http://localhost:3000"})
    assert r.status_code == 200
    client.cookies.clear()


# --------------------------------------------------------------------------- idempotency


async def test_idempotency_key_replays_instead_of_repeating(client):
    u = await make_user(client)
    key = f"idem-{uuid.uuid4().hex}"
    body = {"kind": "support", "subject": "Double click", "body": "Sent twice by a flaky network."}
    h = {**u["headers"], "idempotency-key": key}
    a = await client.post("/api/v1/support/tickets", json=body, headers=h)
    b = await client.post("/api/v1/support/tickets", json=body, headers=h)
    assert a.status_code == b.status_code == 200 and a.json()["id"] == b.json()["id"]
    assert b.headers.get("idempotent-replayed") == "true"
    async with get_sessionmaker()() as db:
        n = (await db.execute(select(SupportTicket).where(SupportTicket.user_id == uuid.UUID(u["id"])))).scalars().all()
    assert len(n) == 1
    r = await client.post("/api/v1/support/tickets", json={**body, "subject": "Different"}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "idempotency_key_reused"
    other = await make_user(client)  # keys are per user
    r = await client.post("/api/v1/support/tickets", json=body, headers={**other["headers"], "idempotency-key": key})
    assert r.status_code == 200 and r.json()["id"] != a.json()["id"]


# --------------------------------------------------------------------------- credits: reservations & races


async def test_reserved_credits_count_against_the_limit(client):
    from app.services import usage

    u = await make_user(client, plan="free")  # 60 credits
    uid = uuid.UUID(u["id"])
    async with get_sessionmaker()() as db:
        db.add(GenerationJob(type="lesson_generation", owner_id=uid, status="queued", credits_reserved=50,
                             payload={}))
        await db.commit()
    async with get_sessionmaker()() as db:
        user = await db.get(User, uid)
        with pytest.raises(LimitExceeded) as e:
            await usage.check(db, user, "credits", 20)
        assert e.value.details["reserved"] == 50
        await usage.check(db, user, "credits", 10)  # 50 held + 10 fits exactly


async def test_concurrent_checks_cannot_both_spend_the_last_credits(client):
    from app.jobs.queue import enqueue
    from app.services import usage

    u = await make_user(client, plan="free")
    uid = uuid.UUID(u["id"])
    results: list[str] = []
    first_checked = asyncio.Event()

    async def spend(hold: bool):
        async with get_sessionmaker()() as db:
            user = await db.get(User, uid)
            try:
                await usage.check(db, user, "credits", 40)
                await enqueue(db, "document_generation", {"n": str(uuid.uuid4())}, owner_id=uid, credits_reserved=40)
                if hold:
                    first_checked.set()
                    await asyncio.sleep(0.3)  # the second request arrives while this one is mid-transaction
                await db.commit()
                results.append("ok")
            except LimitExceeded:
                results.append("limit")

    async def second():
        await first_checked.wait()
        await spend(False)

    await asyncio.gather(spend(True), second())
    assert sorted(results) == ["limit", "ok"]


async def test_daily_generation_limit(client):
    from app.services import usage

    u = await make_user(client, plan="free")
    uid = uuid.UUID(u["id"])
    async with setting("plan_limits", {"*": {"daily_generations": 2}, "free": {"daily_generations": 2}}):
        async with get_sessionmaker()() as db:
            for _ in range(2):
                db.add(GenerationJob(type="document_generation", owner_id=uid, status="succeeded", payload={}))
            await db.commit()
            with pytest.raises(LimitExceeded) as e:
                await usage.check_generation_allowed(db, await db.get(User, uid), jobs=1)
        assert e.value.details["resource"] == "daily_generations"


async def test_concurrent_job_limit_is_applied_by_the_worker(client):
    from app.jobs.queue import claim, enqueue

    u = await make_user(client, plan="free")
    uid = uuid.UUID(u["id"])
    async with setting("plan_limits", {"*": {"max_concurrent_jobs": 1}, "free": {"max_concurrent_jobs": 1}}):
        async with get_sessionmaker()() as db:
            db.add(GenerationJob(type="document_generation", owner_id=uid, status="running", payload={}))
            job = await enqueue(db, "document_generation", {"x": uuid.uuid4().hex}, owner_id=uid)
            assert job.max_concurrent == 1
            await db.commit()
        claimed = []
        while (jid := await claim()) is not None:  # drain other queued jobs; ours must be skipped
            claimed.append(jid)
        assert job.id not in claimed


# --------------------------------------------------------------------------- uploads


async def test_upload_size_follows_plan_limit(client):
    u = await make_user(client, plan="free")
    async with setting("plan_limits", {"free": {"max_upload_mb": 1}}):
        big = io.BytesIO(b"%PDF-1.4\n" + b"0" * (2 * 1024 * 1024))
        r = await client.post("/api/v1/uploads", headers=u["headers"], data={"kind": "source"},
                              files={"file": ("big.pdf", big, "application/pdf")})
        assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"


# --------------------------------------------------------------------------- AI circuit breaker


async def test_circuit_breaker_skips_failing_provider():
    from app.ai.service import CircuitBreaker

    b = CircuitBreaker()
    for _ in range(CircuitBreaker.FAILURE_THRESHOLD - 1):
        assert b.failure("openai") is False
    assert b.failure("openai") is True and b.is_open("openai")
    b.open_until["openai"] = 0  # cool-down elapsed: half-open, one more failure re-opens at once
    assert not b.is_open("openai") and b.failure("openai") is True
    b.success("openai")
    assert not b.is_open("openai") and b.failures["openai"] == 0


async def test_routes_skip_open_breaker(monkeypatch):
    from app.ai.service import AIService

    svc = AIService()
    monkeypatch.setattr(svc.settings, "ai_offline_mode", False)
    monkeypatch.setattr(AIService, "live_providers", property(lambda self: ["anthropic", "openai"]))

    async def no_overrides(self):
        return {}

    monkeypatch.setattr(AIService, "_load_overrides", no_overrides)
    assert [r.provider for r in await svc.routes("fast")][:2] == ["anthropic", "openai"]
    svc.breaker.open_until["anthropic"] = 10**12
    assert [r.provider for r in await svc.routes("fast")][0] == "openai"
    svc.breaker.open_until["openai"] = 10**12
    assert await svc.routes("fast") == []


# --------------------------------------------------------------------------- health


async def test_health_ready_status(client):
    h = (await client.get("/api/v1/health")).json()
    assert h["status"] == "ok" and "version" in h and "database" not in h
    r = await client.get("/api/v1/ready")
    assert r.status_code == 200 and r.json()["checks"]["database"]["ok"] is True
    s = (await client.get("/api/v1/status")).json()
    assert s["status"] in ("operational", "degraded") and "ai_generation" in s["components"]
    staff = await make_staff(client, "support")
    sh = (await client.get("/api/v1/admin/system/health", headers=staff["headers"])).json()
    assert "queue" in sh and "providers" in sh
