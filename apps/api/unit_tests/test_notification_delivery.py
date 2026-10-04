"""Launch email behavior with no database, provider credentials, or real delivery."""
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from app.core.config import Settings
from app.core.db import utcnow
from app.services import notifications, notify


@pytest.fixture
def settings(monkeypatch):
    settings = Settings(_env_file=None, environment="test", resend_api_key="re_test_fake",
                        email_from="Clastio <mail@example.com>", public_web_url="https://app.example.com")
    monkeypatch.setattr(notify, "get_settings", lambda: settings)
    monkeypatch.setattr(notifications, "get_settings", lambda: settings)
    return settings


def outbox(*, user_id=None, template="welcome", subject="Welcome", **changes):
    return SimpleNamespace(id=uuid.uuid4(), user_id=user_id, attempts=0, to_email="teacher@example.com",
                           template=template, subject=subject, body_text="Hello", status="queued",
                           created_at=utcnow(), sent_at=None, last_error=None, **changes)


def fake_result(rows):
    return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rows))


def delivery_fixture(monkeypatch, rows, *, user=None):
    db = AsyncMock()
    db.__aenter__.return_value = db
    db.execute.return_value = fake_result(rows)
    db.get.return_value = user
    monkeypatch.setattr(notify, "get_sessionmaker", lambda: lambda: db)
    remote = AsyncMock()
    remote.__aenter__.return_value = remote
    remote.post.return_value = httpx.Response(200)
    monkeypatch.setattr(notify.httpx, "AsyncClient", lambda **kwargs: remote)
    return db, remote


async def test_missing_production_provider_keeps_mail_recoverable(monkeypatch, settings):
    settings.environment = "production"
    settings.resend_api_key, settings.smtp_url = None, None
    row = outbox()
    db, remote = delivery_fixture(monkeypatch, [row])
    before = utcnow()
    assert await notify.send_pending_emails() == 0
    assert row.status == "queued" and row.attempts == 0 and row.sent_at is None
    assert row.send_after >= before + timedelta(minutes=5)
    assert "not sent" in row.last_error
    remote.post.assert_not_awaited()
    db.commit.assert_awaited_once()


async def test_development_without_provider_only_logs(monkeypatch, settings):
    settings.resend_api_key, settings.smtp_url = None, None
    row = outbox()
    _, remote = delivery_fixture(monkeypatch, [row])
    assert await notify.send_pending_emails() == 0
    assert row.status == "logged" and "not sent" in row.last_error
    remote.post.assert_not_awaited()


async def test_one_invalid_header_does_not_block_other_deliveries(monkeypatch, settings):
    bad, good = outbox(), outbox(subject="Slides\r\nBcc: hidden@example.com")
    bad.to_email = "teacher@example.com\nBcc: injected@example.com"
    _, remote = delivery_fixture(monkeypatch, [bad, good])
    assert await notify.send_pending_emails() == 1
    assert bad.status == "queued" and bad.attempts == 1 and bad.last_error
    assert good.status == "sent"
    assert remote.post.await_count == 1
    assert remote.post.call_args.kwargs["json"]["subject"] == "Slides Bcc: hidden@example.com"
    assert remote.post.call_args.kwargs["json"]["to"] == ["teacher@example.com"]


@pytest.mark.parametrize("restriction", ["opt_out", "withdraw_consent", "inactive", "email_changed"])
async def test_queued_updates_recheck_current_account_and_consent(monkeypatch, settings, restriction):
    user = SimpleNamespace(id=uuid.uuid4(), status="active", email="teacher@example.com", email_verified=True)
    if restriction == "inactive":
        user.status = "pending_deletion"
    elif restriction == "email_changed":
        user.email = "new@example.com"
    row = outbox(user_id=user.id, template="product_update")
    _, remote = delivery_fixture(monkeypatch, [row], user=user)
    prefs = notifications.default_prefs()
    prefs["announcement"]["email"] = restriction != "opt_out"
    monkeypatch.setattr(notifications, "get_prefs", AsyncMock(return_value=prefs))
    monkeypatch.setattr("app.services.legal.latest_consents", AsyncMock(return_value={
        "marketing_email": {"granted": restriction != "withdraw_consent"}}))
    assert await notify.send_pending_emails() == 0
    assert row.status == "logged" and row.sent_at is None and "suppressed" in row.last_error
    remote.post.assert_not_awaited()


async def test_opted_in_ppt_completion_and_security_notice_are_delivered(monkeypatch, settings):
    user = SimpleNamespace(id=uuid.uuid4(), status="active", email="teacher@example.com", email_verified=True)
    rows = [outbox(user_id=user.id, template="lesson_ready"), outbox(user_id=user.id, template="password_changed")]
    _, remote = delivery_fixture(monkeypatch, rows, user=user)
    prefs = notifications.default_prefs()
    prefs["product"]["email"] = True
    monkeypatch.setattr(notifications, "get_prefs", AsyncMock(return_value=prefs))
    assert await notify.send_pending_emails() == 2
    assert remote.post.await_count == 2 and all(row.status == "sent" for row in rows)


async def test_completion_email_is_cancelled_if_preference_changes(monkeypatch, settings):
    user = SimpleNamespace(id=uuid.uuid4(), status="active", email="teacher@example.com", email_verified=True)
    row = outbox(user_id=user.id, template="lesson_ready")
    _, remote = delivery_fixture(monkeypatch, [row], user=user)
    monkeypatch.setattr(notifications, "get_prefs", AsyncMock(return_value=notifications.default_prefs()))
    assert await notify.send_pending_emails() == 0
    assert row.status == "logged"
    remote.post.assert_not_awaited()


async def test_email_only_event_dedupes_without_a_visible_notice(monkeypatch, settings):
    user = SimpleNamespace(id=uuid.uuid4(), status="active", name="Teacher", email="teacher@example.com")
    prefs = notifications.default_prefs()
    prefs["product"] = {"in_app": False, "email": True}
    monkeypatch.setattr(notifications, "get_prefs", AsyncMock(return_value=prefs))
    insert = AsyncMock(side_effect=[True, False])
    email = Mock()
    monkeypatch.setattr(notifications, "notify", insert)
    monkeypatch.setattr(notifications, "queue_email", email)
    db = AsyncMock()
    for _ in range(2):
        await notifications.send(db, user, "lesson_ready", dedupe_key="job:one", title="Fractions", id="lesson")
    assert email.call_count == 1
    assert all(call.kwargs["visible"] is False for call in insert.call_args_list)
    assert email.call_args.kwargs["link"] == "https://app.example.com/lessons/lesson"


async def test_hidden_dedupe_row_contains_no_teacher_content():
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(rowcount=1)
    assert await notify.notify(db, uuid.uuid4(), "product", "Private topic", "Private details", "/lesson",
                               dedupe_key="once", visible=False)
    values = db.execute.call_args.args[0].compile().params
    assert values["type"] == notify.EMAIL_DEDUPE_TYPE
    assert values["title"] == values["body"] == "" and values["link"] is None
    assert values["read_at"] is not None


async def test_dismissing_a_reminder_preserves_its_delivery_marker():
    from app.api.routes.account import delete_notification

    user, nid, db = SimpleNamespace(id=uuid.uuid4()), uuid.uuid4(), AsyncMock()
    db.execute.return_value = SimpleNamespace(rowcount=1)
    assert await delete_notification(nid, user, db) == {"ok": True}
    assert db.execute.await_count == 1
    statement = db.execute.call_args.args[0]
    assert statement.is_update
    values = statement.compile().params
    assert values["type"] == notify.EMAIL_DEDUPE_TYPE
    assert values["title"] == values["body"] == "" and values["link"] is None
    assert values["read_at"] is not None
    db.commit.assert_awaited_once()


async def test_plain_notice_is_deleted_but_a_hidden_marker_cannot_be_removed():
    from app.api.routes.account import delete_notification
    from app.core.errors import NotFound

    user, db = SimpleNamespace(id=uuid.uuid4()), AsyncMock()
    db.execute.side_effect = [SimpleNamespace(rowcount=0), SimpleNamespace(rowcount=1)]
    assert await delete_notification(uuid.uuid4(), user, db) == {"ok": True}
    assert db.execute.call_args.args[0].is_delete
    db.execute.side_effect = [SimpleNamespace(rowcount=0), SimpleNamespace(rowcount=0)]
    with pytest.raises(NotFound):
        await delete_notification(uuid.uuid4(), user, db)


async def test_review_invitation_respects_both_delivery_preferences(monkeypatch, settings):
    user = SimpleNamespace(id=uuid.uuid4(), status="active")
    prefs = notifications.default_prefs()
    prefs["feedback"] = {"in_app": False, "email": False}
    monkeypatch.setattr(notifications, "get_prefs", AsyncMock(return_value=prefs))
    insert, email = AsyncMock(return_value=True), Mock()
    monkeypatch.setattr(notifications, "notify", insert)
    monkeypatch.setattr(notifications, "queue_email", email)
    await notifications.send(AsyncMock(), user, "review_invitation", dedupe_key="review:2026-10")
    assert insert.call_args.kwargs["visible"] is False
    email.assert_not_called()


async def test_renewed_manual_access_gets_a_new_reminder_and_zero_price_stays_zero(monkeypatch, settings):
    now, uid = utcnow(), uuid.uuid4()
    user = SimpleNamespace(id=uid)
    plan = SimpleNamespace(code="pro", name="Pro", price_monthly_aed=249, price_annual_aed=2490)
    grant = SimpleNamespace(id=uuid.uuid4(), plan_code="pro", provider="manual", status="active",
                            current_period_end=now + timedelta(days=5))
    paid = SimpleNamespace(id=uuid.uuid4(), plan_code="pro", provider="stripe", status="active", interval="month",
                           cancel_at_period_end=False, current_period_end=now + timedelta(days=2), price_aed=0)
    db = AsyncMock()
    db.__aenter__.return_value = db
    monkeypatch.setattr(notifications, "get_sessionmaker", lambda: lambda: db)
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(notifications, "send", send)
    keys = []
    for _ in range(2):
        db.execute.side_effect = [fake_result([plan]), SimpleNamespace(all=lambda: [(grant, user), (paid, user)]),
                                  SimpleNamespace(all=lambda: [])]
        await notifications.run_reminders()
        grant_calls = [call for call in send.call_args_list if call.args[2] == "grant_expiring"]
        keys.append(grant_calls[-1].kwargs["dedupe_key"])
        grant.current_period_end += timedelta(days=1)
    assert keys[0] != keys[1]
    renewal_calls = [call for call in send.call_args_list if call.args[2] == "renewal_upcoming"]
    assert all(call.kwargs["amount"] == "AED 0" for call in renewal_calls)
