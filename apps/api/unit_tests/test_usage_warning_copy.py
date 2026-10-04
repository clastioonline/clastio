"""Credit warnings distinguish a monthly allowance from the whole no-card trial."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.db import utcnow
from app.services import notify, usage


@pytest.mark.parametrize("trial,spent,title", [
    (False, 30, "You've used 50% of this month's credits"),
    (False, 60, "You've used all your credits this month"),
    (True, 30, "You've used 50% of your trial credits"),
    (True, 60, "You've used all your trial credits"),
])
async def test_usage_warning_copy_keeps_correct_period(monkeypatch, trial, spent, title):
    uid = uuid.uuid4()
    user = SimpleNamespace(id=uid, role="teacher")
    plan = SimpleNamespace(name="Teacher Pro", limits={"credits": 60})
    sub = SimpleNamespace(provider="trial", current_period_start=utcnow()) if trial else None
    db = AsyncMock()
    db.get.return_value = user
    monkeypatch.setattr(usage, "get_plan", AsyncMock(return_value=(plan, sub)))
    monkeypatch.setattr(usage, "used", AsyncMock(return_value=spent))
    notice, email = AsyncMock(return_value=True), Mock()
    monkeypatch.setattr(notify, "notify", notice)
    monkeypatch.setattr(notify, "queue_email", email)
    monkeypatch.setattr("app.core.config.get_settings", lambda: SimpleNamespace(public_web_url="https://app.example.com"))
    await usage.warn_usage(db, uid, "credits")
    assert notice.call_args.args[3] == title
    body = notice.call_args.args[4]
    assert ("for the entire trial" in body) is trial
    if spent == 60:
        template = email.call_args.args[2]
        assert template == ("trial_usage_warning" if trial else "usage_warning")
        subject, text = notify.TEMPLATES[template]
        assert ("trial" in subject) is trial
        assert ("next month" in text) is not trial
    else:
        email.assert_not_called()
