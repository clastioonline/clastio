"""Signed-in devices. The access token carries the session id (`sid`); every request checks the session is live,
so logging out, "log out everywhere", password changes and admin force-logout take effect immediately."""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.request_meta import client_ip, parse_user_agent, user_agent
from app.core.security import COOKIE_NAME, create_access_token
from app.models import User, UserSession
from app.services.events import security_event
from app.services.notify import notify, queue_email

ACTIVITY_WRITE_EVERY = timedelta(minutes=5)


def _ip_prefix(ip: str | None) -> str:
    if not ip:
        return ""
    return ".".join(ip.split(".")[:3]) if "." in ip else ":".join(ip.split(":")[:4])


async def start_session(db: AsyncSession, user: User, request: Request | None, response: Response | None,
                        method: str = "password") -> tuple[UserSession, str]:
    """Create a session, detect a new device, and set the HttpOnly cookie. Returns (session, token)."""
    s = get_settings()
    ua = user_agent(request)
    ip = client_ip(request)
    meta = parse_user_agent(ua)
    now = utcnow()
    previous = (await db.execute(select(UserSession).where(UserSession.user_id == user.id)
                                 .order_by(UserSession.created_at.desc()).limit(50))).scalars().all()
    sess = UserSession(user_id=user.id, ip=ip, user_agent=ua, method=method, created_at=now, last_active_at=now,
                       expires_at=now + timedelta(minutes=s.access_token_minutes), **meta)
    db.add(sess)
    await db.flush()
    known = any(p.browser == meta["browser"] and p.os == meta["os"] and _ip_prefix(p.ip) == _ip_prefix(ip)
                for p in previous)
    if previous and not known and meta["device_type"] != "bot":
        device = f"{meta['browser']} on {meta['os']}"
        security_event(db, "new_device", user_id=user.id, request=request, device=device)
        await notify(db, user.id, "security", "New sign-in", f"{device} signed in to your account.", "/settings/security")
        queue_email(db, user, "login_alert", link=f"{s.public_web_url}/settings/security", device=device, ip=ip or "unknown")
    token = create_access_token(user.id, extra={"sid": str(sess.id)})
    if response is not None:
        response.set_cookie(COOKIE_NAME, token, httponly=True, secure=s.cookie_secure, samesite="lax",
                            max_age=s.access_token_minutes * 60, path="/")
    return sess, token


async def load_active(db: AsyncSession, session_id: str | None, user_id: uuid.UUID) -> UserSession | None:
    try:
        sid = uuid.UUID(session_id or "")
    except ValueError:
        return None
    sess = await db.get(UserSession, sid)
    if sess is None or sess.user_id != user_id or sess.revoked_at is not None or sess.expires_at <= utcnow():
        return None
    return sess


async def touch(db: AsyncSession, sess: UserSession, user: User) -> None:
    """Record activity at most every few minutes so busy users don't write on every request."""
    now = utcnow()
    if now - sess.last_active_at >= ACTIVITY_WRITE_EVERY:
        sess.last_active_at = now
        user.last_active_at = now
        await db.commit()


async def revoke(db: AsyncSession, user_id: uuid.UUID, *, session_id: uuid.UUID | None = None,
                 except_id: uuid.UUID | None = None, reason: str = "user") -> int:
    q = update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if session_id:
        q = q.where(UserSession.id == session_id)
    if except_id:
        q = q.where(UserSession.id != except_id)
    res = await db.execute(q.values(revoked_at=utcnow(), revoked_reason=reason))
    return res.rowcount or 0


def session_out(s: UserSession, current_id: uuid.UUID | None = None) -> dict:
    return {"id": str(s.id), "browser": s.browser, "os": s.os, "device_type": s.device_type, "ip": s.ip,
            "method": s.method, "created_at": s.created_at.isoformat(), "last_active_at": s.last_active_at.isoformat(),
            "expires_at": s.expires_at.isoformat(), "revoked_at": s.revoked_at.isoformat() if s.revoked_at else None,
            "revoked_reason": s.revoked_reason, "current": s.id == current_id}
