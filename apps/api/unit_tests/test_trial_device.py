from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import Request, Response
from pydantic import ValidationError

from app.api.routes.rewards import ProgramIn, TaskIn
from app.services.rewards import month_end, task_open
from app.services.trial_device import COOKIE, cookie_digest, ensure_cookie


def test_signed_random_cookie_rejects_tampering_and_persists_browser_identity():
    request = Request({"type": "http", "headers": []})
    response = Response()
    digest = ensure_cookie(request, response)
    value = response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    assert value not in digest and len(digest) == 64
    assert cookie_digest(value) == digest
    assert cookie_digest(value[:-1] + ("a" if value[-1] != "a" else "b")) is None
    tampered = Request({"type": "http", "headers": [(b"cookie", f"{COOKIE}={value[:-1]}x".encode())]})
    from app.core.errors import AppError

    with pytest.raises(AppError) as error:
        ensure_cookie(tampered, Response(), strict=True)
    assert error.value.code == "browser_verification_failed"
    ignored = Response()
    assert ensure_cookie(tampered, ignored) is None
    assert "set-cookie" not in ignored.headers
    assert cookie_digest("invented-cookie") is None
    repeated = Request({"type": "http", "headers": [(b"cookie", f"{COOKIE}={value}".encode())]})
    assert ensure_cookie(repeated, Response()) == digest
    assert "HttpOnly" in response.headers["set-cookie"] and "Max-Age=31536000" in response.headers["set-cookie"]


@pytest.mark.parametrize("date,expected", [(datetime(2026, 12, 31, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC)),
                                         (datetime(2026, 2, 1, tzinfo=UTC), datetime(2026, 3, 1, tzinfo=UTC))])
def test_rewards_expire_at_calendar_month_boundary(date, expected):
    assert month_end(date) == expected


def test_unpublished_and_expired_tasks_are_closed():
    now = datetime.now(UTC)
    task = SimpleNamespace(published=False, starts_at=None, ends_at=None)
    assert not task_open(task, now)
    task.published, task.ends_at = True, now
    assert not task_open(task, now)
    task.ends_at = None
    assert task_open(task, now)


def test_staff_configuration_cannot_remove_caps_or_skip_task_policy():
    with pytest.raises(ValidationError):
        ProgramIn(daily_credits=100000, reason="test update")
    with pytest.raises(ValidationError):
        TaskIn(title="Quality feedback", instructions="Give honest feedback on the lesson slides.", credits=5)
    with pytest.raises(ValidationError):
        TaskIn(title="Quality feedback", instructions="Give honest feedback on the lesson slides.", credits=500, policy_acknowledged=True)
