"""Deployment regressions: reject unsafe settings and preserve useful outage probes."""

import pytest

from app.core.config import Settings


def production_settings(**overrides):
    values = dict(environment="production", secret_key="a" * 48, cookie_secure=True,
                  public_web_url="https://lessons.example.com", run_jobs_inline=False, redis_url="redis://localhost:6379/0")
    return Settings(_env_file=None, **(values | overrides))


@pytest.mark.parametrize("overrides, field", [
    ({"secret_key": "short"}, "SECRET_KEY"),
    ({"cookie_secure": False}, "COOKIE_SECURE"),
    ({"public_web_url": "http://lessons.example.com"}, "PUBLIC_WEB_URL"),
    ({"public_web_url": "https://localhost"}, "PUBLIC_WEB_URL"),
    ({"public_web_url": "https://lessons.example.com/path"}, "PUBLIC_WEB_URL"),
    ({"redis_url": None}, "REDIS_URL"),
    ({"run_jobs_inline": True}, "RUN_JOBS_INLINE"),
])
def test_unsafe_production_settings(overrides, field):
    with pytest.raises(RuntimeError, match=field):
        production_settings(**overrides).validate_production()


def test_valid_production_settings():
    production_settings().validate_production()


async def test_health_probes_do_not_read_application_settings(client, monkeypatch):
    from app.services import settings

    async def unavailable(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(settings, "get_setting_cached", unavailable)
    assert (await client.get("/api/v1/health")).status_code == 200
    assert (await client.get("/api/v1/ready")).status_code == 200


async def test_authenticated_content_is_not_cacheable(client, teacher):
    response = await client.get("/api/v1/projects", headers=teacher["headers"])
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"


async def test_non_bearer_header_does_not_bypass_cookie_csrf(client):
    from starlette.requests import Request

    from app.core.http import _csrf_rejected

    request = Request({"type": "http", "method": "POST", "path": "/api/v1/me",
                       "headers": [(b"cookie", b"ata_session=example"),
                                   (b"authorization", b"Basic arbitrary"),
                                   (b"origin", b"https://untrusted.example")]})
    assert _csrf_rejected(request)


async def test_whatsapp_simulator_is_disabled_in_production(client, teacher, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "environment", "production")
    status = await client.get("/api/v1/whatsapp", headers=teacher["headers"])
    assert status.status_code == 200
    assert status.json()["simulation_enabled"] is False
    response = await client.post("/api/v1/whatsapp/simulate", headers=teacher["headers"], json={"text": "hello"})
    assert response.status_code == 403


async def test_readiness_rejects_unmigrated_production_database(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "environment", "production")
    response = await client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["schema"]["ok"] is False
