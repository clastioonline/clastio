"""Sessions, account status, password flows, RBAC, audit trail, credit adjustments and account deletion."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text

from app.core.db import get_sessionmaker
from app.core.security import create_access_token
from app.models import AuditLog, Consent, CreditLedger, EmailOutbox, Payment, SecurityEvent, User, UserSession
from tests.conftest import make_staff, make_user


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, email, password="correct-horse-1", ua="pytest-agent"):
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password},
                          headers={"user-agent": ua})
    client.cookies.clear()
    return r


# --------------------------------------------------------------------------- signup & consent


async def test_signup_requires_terms_and_records_versioned_consent(client):
    email = f"t-{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-1", "name": "A"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "terms_required"
    r = await client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-1", "name": "A",
                                                        "accept_terms": True, "marketing_email": False})
    assert r.status_code == 200
    client.cookies.clear()
    uid = uuid.UUID(r.json()["user"]["id"])
    async with get_sessionmaker()() as db:
        rows = (await db.execute(select(Consent).where(Consent.user_id == uid))).scalars().all()
    kinds = {c.kind: c for c in rows}
    assert {"terms", "privacy", "acceptable_use"} <= set(kinds)
    current = (await client.get("/api/v1/legal/terms")).json()["version"]
    assert kinds["terms"].version == current and kinds["terms"].document_id and kinds["terms"].granted
    assert kinds["terms"].method == "signup_checkbox"
    assert kinds["marketing_email"].granted is False  # marketing is a separate, unticked choice
    assert r.json()["user"]["email_verified"] is False


async def test_weak_and_common_passwords_rejected(client):
    for pw in ("password123", "short1"):
        r = await client.post("/api/v1/auth/signup", json={"email": f"w-{uuid.uuid4().hex[:6]}@example.com",
                                                            "password": pw, "name": "W", "accept_terms": True})
        assert r.status_code == 422


# --------------------------------------------------------------------------- sessions


async def test_logout_revokes_the_token_immediately(client):
    u = await make_user(client)
    assert (await client.get("/api/v1/auth/me", headers=u["headers"])).status_code == 200
    assert (await client.post("/api/v1/auth/logout", headers=u["headers"])).status_code == 200
    client.cookies.clear()
    r = await client.get("/api/v1/auth/me", headers=u["headers"])
    assert r.status_code == 401  # a copied token stops working at once, not when it expires


async def test_logout_all_and_session_list(client):
    u = await make_user(client)
    second = (await _login(client, u["email"], ua="Mozilla/5.0 (Macintosh) Firefox/130.0")).json()["token"]
    listing = (await client.get("/api/v1/auth/sessions", headers=bearer(second))).json()["items"]
    assert len(listing) == 2 and sum(s["current"] for s in listing) == 1
    other = next(s for s in listing if not s["current"])
    assert (await client.delete(f"/api/v1/auth/sessions/{other['id']}", headers=bearer(second))).status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=u["headers"])).status_code == 401
    assert (await client.post("/api/v1/auth/logout-all", headers=bearer(second))).status_code == 200
    client.cookies.clear()
    assert (await client.get("/api/v1/auth/me", headers=bearer(second))).status_code == 401


async def test_token_without_session_is_rejected(client):
    u = await make_user(client)
    forged = create_access_token(uuid.UUID(u["id"]))  # valid signature, but no live session
    assert (await client.get("/api/v1/auth/me", headers=bearer(forged))).status_code == 401


async def test_new_device_raises_security_event_and_alert(client):
    u = await make_user(client)
    await _login(client, u["email"], ua="Mozilla/5.0 (Linux; Android 14) Chrome/128.0 Mobile")
    async with get_sessionmaker()() as db:
        ev = (await db.execute(select(SecurityEvent).where(SecurityEvent.user_id == uuid.UUID(u["id"]),
                                                           SecurityEvent.type == "new_device"))).scalars().all()
        mails = (await db.execute(select(EmailOutbox).where(EmailOutbox.user_id == uuid.UUID(u["id"]),
                                                            EmailOutbox.template == "login_alert"))).scalars().all()
    assert ev and mails


async def test_failed_logins_are_recorded(client):
    u = await make_user(client)
    await _login(client, u["email"], password="wrong-password-x")
    async with get_sessionmaker()() as db:
        ev = (await db.execute(select(SecurityEvent).where(SecurityEvent.user_id == uuid.UUID(u["id"]),
                                                           SecurityEvent.type == "login_failed"))).scalars().first()
    assert ev and ev.severity == "warning"


# --------------------------------------------------------------------------- email verification & passwords


async def test_email_verification_token(client):
    u = await make_user(client)
    token = create_access_token(uuid.UUID(u["id"]), minutes=60, extra={"typ": "verify", "em": u["email"]})
    r = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert r.status_code == 200
    me = (await client.get("/api/v1/auth/me", headers=u["headers"])).json()["user"]
    assert me["email_verified"] is True
    # A login token can't be used as a verification token.
    r = await client.post("/api/v1/auth/verify-email", json={"token": u["token"]})
    assert r.status_code == 400


async def test_forgot_password_does_not_reveal_accounts(client):
    a = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody-here@example.com"})
    u = await make_user(client)
    b = await client.post("/api/v1/auth/forgot-password", json={"email": u["email"]})
    assert a.status_code == b.status_code == 200 and a.json() == b.json()


async def test_reset_password_is_single_use_and_signs_out_everywhere(client):
    from app.api.routes.auth import reset_link

    u = await make_user(client)
    async with get_sessionmaker()() as db:
        user = await db.get(User, uuid.UUID(u["id"]))
        token = reset_link(user).split("token=")[1]
    r = await client.post("/api/v1/auth/reset-password", json={"token": token, "password": "brand-new-pass-9"})
    assert r.status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=u["headers"])).status_code == 401
    r = await client.post("/api/v1/auth/reset-password", json={"token": token, "password": "another-pass-77"})
    assert r.status_code == 400  # the link stopped working once the password changed
    assert (await _login(client, u["email"], password="brand-new-pass-9")).status_code == 200


async def test_change_password_keeps_this_device_only(client):
    u = await make_user(client)
    other = (await _login(client, u["email"], ua="Other/1.0")).json()["token"]
    r = await client.post("/api/v1/auth/change-password", headers=u["headers"],
                          json={"current_password": "wrong-one-123", "new_password": "fresh-password-1"})
    assert r.status_code in (400, 401)
    r = await client.post("/api/v1/auth/change-password", headers=u["headers"],
                          json={"current_password": "correct-horse-1", "new_password": "fresh-password-1"})
    assert r.status_code == 200
    client.cookies.clear()
    assert (await client.get("/api/v1/auth/me", headers=u["headers"])).status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=bearer(other))).status_code == 401


# --------------------------------------------------------------------------- account status


async def test_suspension_takes_effect_immediately_and_is_audited(client):
    admin = await make_staff(client, "support")
    u = await make_user(client)
    r = await client.post(f"/api/v1/admin/users/{u['id']}/status", headers=admin["headers"],
                          json={"status": "suspended", "reason": "Chargeback investigation"})
    assert r.status_code == 200 and r.json()["sessions_revoked"] >= 1
    assert (await client.get("/api/v1/auth/me", headers=u["headers"])).status_code == 401
    r = await _login(client, u["email"])
    assert r.status_code == 403 and r.json()["error"]["code"] == "account_suspended"
    # Support can't ban; that needs users.ban.
    r = await client.post(f"/api/v1/admin/users/{u['id']}/status", headers=admin["headers"],
                          json={"status": "banned", "reason": "Abuse"})
    assert r.status_code == 403
    r = await client.post(f"/api/v1/admin/users/{u['id']}/status", headers=admin["headers"],
                          json={"status": "active", "reason": "Resolved"})
    assert r.status_code == 200
    assert (await _login(client, u["email"])).status_code == 200
    async with get_sessionmaker()() as db:
        rows = (await db.execute(select(AuditLog).where(AuditLog.target == u["id"],
                                                        AuditLog.action.like("user.%")))).scalars().all()
    suspended = next(a for a in rows if a.action == "user.suspended")
    assert suspended.before["status"] == "active" and suspended.after["status"] == "suspended"
    assert suspended.reason == "Chargeback investigation" and suspended.actor_id == uuid.UUID(admin["id"])


async def test_status_change_requires_a_reason(client):
    admin = await make_staff(client, "moderator")
    u = await make_user(client)
    r = await client.post(f"/api/v1/admin/users/{u['id']}/status", headers=admin["headers"],
                          json={"status": "banned"})
    assert r.status_code == 422


# --------------------------------------------------------------------------- RBAC


@pytest.mark.parametrize("role,path,method,allowed", [
    ("analyst", "/api/v1/admin/metrics", "get", True),
    ("analyst", "/api/v1/admin/settings", "get", False),
    ("analyst", "/api/v1/admin/audit-logs", "get", False),
    ("finance", "/api/v1/admin/subscriptions", "get", True),
    ("finance", "/api/v1/admin/security-events", "get", False),
    ("support", "/api/v1/admin/security-events", "get", True),
    ("support", "/api/v1/admin/export/users", "get", False),
    ("moderator", "/api/v1/admin/plans", "get", False),
    ("admin", "/api/v1/admin/audit-logs", "get", True),
    ("admin", "/api/v1/admin/staff", "get", True),
])
async def test_role_permissions_are_enforced_server_side(client, role, path, method, allowed):
    s = await make_staff(client, role)
    r = await getattr(client, method)(path, headers=s["headers"])
    assert (r.status_code == 200) is allowed, (role, path, r.status_code, r.text[:200])
    if not allowed:
        assert r.status_code == 403


async def test_teachers_get_no_admin_access(client):
    u = await make_user(client)
    for path in ("/api/v1/admin/users", "/api/v1/admin/audit-logs", "/api/v1/admin/roles", "/api/v1/admin/search?q=ab"):
        assert (await client.get(path, headers=u["headers"])).status_code == 403


async def test_only_super_admin_manages_staff_and_last_super_admin_is_protected(client):
    admin = await make_staff(client, "admin")
    sup = await make_staff(client, "super_admin")
    u = await make_user(client)
    body = {"admin_role": "support", "reason": "New support hire"}
    assert (await client.put(f"/api/v1/admin/users/{u['id']}/staff-role", headers=admin["headers"],
                             json=body)).status_code == 403
    r = await client.put(f"/api/v1/admin/users/{u['id']}/staff-role", headers=sup["headers"], json=body)
    assert r.status_code == 200 and r.json()["admin_role"] == "support"
    # An admin can't suspend another staff member.
    r = await client.post(f"/api/v1/admin/users/{u['id']}/status", headers=admin["headers"],
                          json={"status": "suspended", "reason": "test"})
    assert r.status_code == 403
    # Staff can't change their own role.
    r = await client.put(f"/api/v1/admin/users/{sup['id']}/staff-role", headers=sup["headers"],
                         json={"admin_role": None, "reason": "stepping down"})
    assert r.status_code == 409
    async with get_sessionmaker()() as db:
        ev = (await db.execute(select(SecurityEvent).where(SecurityEvent.user_id == uuid.UUID(u["id"]),
                                                           SecurityEvent.type == "admin_role_changed"))).scalars().first()
    assert ev and ev.severity == "critical"


# --------------------------------------------------------------------------- audit log is append-only


async def test_audit_log_cannot_be_edited_or_deleted(client):
    admin = await make_staff(client, "super_admin")
    u = await make_user(client)
    await client.post(f"/api/v1/admin/users/{u['id']}/notes", headers=admin["headers"], json={"body": "VIP"})
    from sqlalchemy.exc import DBAPIError

    async with get_sessionmaker()() as db:
        row_id = (await db.execute(select(AuditLog.id).where(AuditLog.target == u["id"]))).scalars().first()
    for sql, params in (("UPDATE audit_logs SET action = 'nothing' WHERE id = :id", {"id": row_id}),
                        ("DELETE FROM audit_logs WHERE id = :id", {"id": row_id}),
                        ("DELETE FROM consents WHERE user_id = :u", {"u": uuid.UUID(u["id"])})):
        async with get_sessionmaker()() as db:
            with pytest.raises(DBAPIError, match="append-only"):
                await db.execute(text(sql), params)


# --------------------------------------------------------------------------- credits


async def test_credit_adjustment_needs_permission_and_reason_and_is_typed(client):
    finance = await make_staff(client, "finance")
    support = await make_staff(client, "support")
    u = await make_user(client, plan="free")
    before = (await client.get("/api/v1/me/usage", headers=u["headers"])).json()["usage"]["credits"]["used"]
    body = {"resource": "credits", "amount": 25, "reason": "Goodwill after outage"}
    assert (await client.post(f"/api/v1/admin/users/{u['id']}/credits", headers=support["headers"],
                              json=body)).status_code == 403
    assert (await client.post(f"/api/v1/admin/users/{u['id']}/credits", headers=finance["headers"],
                              json={**body, "reason": ""})).status_code == 422
    r = await client.post(f"/api/v1/admin/users/{u['id']}/credits", headers=finance["headers"], json=body)
    assert r.status_code == 200 and r.json()["ledger"]["event_type"] == "CREDIT_ADMIN_GRANT"
    after = (await client.get("/api/v1/me/usage", headers=u["headers"])).json()["usage"]["credits"]["used"]
    assert after == before - 25
    r = await client.post(f"/api/v1/admin/users/{u['id']}/credits", headers=finance["headers"],
                          json={"resource": "credits", "amount": -5, "reason": "Duplicate grant"})
    assert r.json()["ledger"]["event_type"] == "CREDIT_ADJUSTMENT"
    async with get_sessionmaker()() as db:
        rows = (await db.execute(select(CreditLedger).where(CreditLedger.owner_id == uuid.UUID(u["id"]),
                                                            CreditLedger.actor_id.is_not(None)))).scalars().all()
    assert len(rows) == 2 and all(r.actor_id == uuid.UUID(finance["id"]) for r in rows)
    assert {r.meta["reason"] for r in rows} == {"Goodwill after outage", "Duplicate grant"}


# --------------------------------------------------------------------------- admin views


async def test_admin_user_detail_is_logged_as_data_access(client):
    admin = await make_staff(client, "support")
    u = await make_user(client)
    r = await client.get(f"/api/v1/admin/users/{u['id']}", headers=admin["headers"])
    body = r.json()
    assert r.status_code == 200 and body["sessions"] and "password_hash" not in str(body)
    assert "payments" in body  # support holds billing.view
    async with get_sessionmaker()() as db:
        logged = (await db.execute(select(AuditLog).where(AuditLog.action == "data_access.user_profile",
                                                          AuditLog.target == u["id"]))).scalars().first()
    assert logged and logged.actor_id == uuid.UUID(admin["id"])


async def test_user_list_filters_and_cursor(client):
    admin = await make_staff(client, "analyst")
    for _ in range(3):
        await make_user(client, plan="free")
    r = (await client.get("/api/v1/admin/users?limit=2&kind=teacher", headers=admin["headers"])).json()
    assert len(r["items"]) == 2 and r["next_cursor"]
    r2 = (await client.get(f"/api/v1/admin/users?limit=2&kind=teacher&cursor={r['next_cursor']}",
                           headers=admin["headers"])).json()
    assert not {i["id"] for i in r["items"]} & {i["id"] for i in r2["items"]}
    free = (await client.get("/api/v1/admin/users?plan=free&limit=200", headers=admin["headers"])).json()
    assert free["items"] and all(i["plan"] == "free" for i in free["items"])
    assert (await client.get("/api/v1/admin/users?cursor=garbage", headers=admin["headers"])).status_code == 400


async def test_export_is_audited_and_formula_safe(client):
    analyst = await make_staff(client, "analyst")
    await make_user(client, name="=HYPERLINK(\"http://evil\")")
    r = await client.get("/api/v1/admin/export/users?format=csv&days=1", headers=analyst["headers"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "'=HYPERLINK" in r.text and "password" not in r.text.lower()
    assert (await client.get("/api/v1/admin/export/audit_logs", headers=analyst["headers"])).status_code == 403
    async with get_sessionmaker()() as db:
        logged = (await db.execute(select(AuditLog).where(AuditLog.action == "data.export",
                                                          AuditLog.actor_id == uuid.UUID(analyst["id"])))).scalars().all()
    assert logged and logged[0].target_id == "users"


async def test_request_trace_and_search(client):
    admin = await make_staff(client, "admin")
    u = await make_user(client)
    rid = "req_trace_test_0001"
    await client.post(f"/api/v1/admin/users/{u['id']}/notes", headers={**admin["headers"], "x-request-id": rid},
                      json={"body": "note"})
    t = (await client.get(f"/api/v1/admin/trace/{rid}", headers=admin["headers"])).json()
    assert any(a["action"] == "user.note_added" for a in t["audit"])
    s = (await client.get(f"/api/v1/admin/search?q={u['email']}", headers=admin["headers"])).json()
    assert s["users"][0]["id"] == u["id"]


# --------------------------------------------------------------------------- deletion


async def test_account_deletion_locks_now_and_purges_later_keeping_records(client):
    u = await make_user(client)
    uid = uuid.UUID(u["id"])
    async with get_sessionmaker()() as db:
        db.add(Payment(user_id=uid, provider="dodo", provider_ref=f"pay_{uuid.uuid4().hex[:8]}", amount=99,
                       status="paid"))
        await db.commit()
    r = await client.post("/api/v1/me/delete", headers=u["headers"], json={"confirm_email": u["email"]})
    assert r.status_code == 200 and r.json()["status"] == "pending_deletion"
    client.cookies.clear()
    assert (await client.get("/api/v1/auth/me", headers=u["headers"])).status_code == 401
    assert (await _login(client, u["email"])).json()["error"]["code"] == "account_pending_deletion"

    from datetime import timedelta

    from app.core.db import utcnow
    from app.services.lifecycle import purge_due_accounts

    async with get_sessionmaker()() as db:
        user = await db.get(User, uid)
        user.deletion_requested_at = utcnow() - timedelta(days=31)
        await db.commit()
    assert await purge_due_accounts() >= 1
    async with get_sessionmaker()() as db:
        user = await db.get(User, uid)
        assert user.status == "deleted" and user.email.endswith("@deleted.invalid") and user.password_hash is None
        assert (await db.execute(select(Payment).where(Payment.user_id == uid))).scalars().first()
        assert (await db.execute(select(Consent).where(Consent.user_id == uid))).scalars().first()
        assert not (await db.execute(select(UserSession).where(UserSession.user_id == uid))).scalars().first()
