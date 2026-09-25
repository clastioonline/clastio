from __future__ import annotations

import hashlib
import secrets
import uuid
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.deps import DB, CurrentUser
from app.core.errors import AppError
from app.core.permissions import ROLE_LABELS
from app.core.ratelimit import enforce, rate_limit
from app.core.request_meta import client_ip
from app.core.security import (
    COOKIE_NAME,
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import OAuthAccount, TeacherProfile, TrialGrant, User, UserSession
from app.services import legal, sessions
from app.services.events import security_event, track
from app.services.notify import queue_email

router = APIRouter(prefix="/auth", tags=["auth"])

# A few very common passwords; the length rule does most of the work.
COMMON_PASSWORDS = {"password", "password1", "password123", "12345678", "123456789", "qwerty123", "11111111",
                    "iloveyou", "letmein1", "welcome1", "admin123", "abc12345", "teacher1", "school123"}
DISPOSABLE_DOMAINS = {"mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com", "trashmail.com",
                      "yopmail.com", "sharklasers.com", "getnada.com", "dispostable.com", "temp-mail.org"}


def check_password(password: str, email: str) -> None:
    if password.lower() in COMMON_PASSWORDS or password.lower() == email.lower().split("@")[0]:
        raise AppError("weak_password", "Choose a less common password (at least 8 characters).", 422)


def normalised_email_hash(email: str) -> str:
    """Same person, same hash: case, dots and +tags in Gmail addresses are ignored (trial abuse control)."""
    local, _, domain = email.lower().partition("@")
    local = local.split("+", 1)[0]
    if domain in ("gmail.com", "googlemail.com"):
        local, domain = local.replace(".", ""), "gmail.com"
    return hashlib.sha256(f"{local}@{domain}".encode()).hexdigest()


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    # "I agree to the Terms and the Acceptable Use Policy and acknowledge the Privacy Policy" (recorded separately)
    accept_terms: bool = False
    marketing_email: bool = False
    utm: dict[str, str] = Field(default_factory=dict)
    referral_code: str | None = Field(None, max_length=16)
    captcha_token: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


def user_out(u: User) -> dict[str, Any]:
    from app.core.deps import staff_permissions

    perms = sorted(staff_permissions(u))
    return {"id": str(u.id), "email": u.email, "name": u.name, "role": u.role, "locale": u.locale,
            "timezone": u.timezone, "email_verified": u.email_verified, "status": u.status,
            "admin_role": u.admin_role, "admin_role_label": ROLE_LABELS.get(u.admin_role or ""),
            "permissions": perms, "avatar_url": u.avatar_url,
            # Staff run the platform; they have no teacher onboarding.
            "onboarding_completed": bool(perms) or bool(u.profile and u.profile.onboarding_completed)}


async def _load(db, user_id: uuid.UUID) -> User:
    from sqlalchemy.orm import selectinload

    return (await db.execute(select(User).options(selectinload(User.profile)).where(User.id == user_id))
            ).scalars().one()


async def verify_captcha(token: str | None, request: Request) -> None:
    """Cloudflare Turnstile, only when TURNSTILE_SECRET is configured."""
    secret = get_settings().turnstile_secret
    if not secret:
        return
    if not token:
        raise AppError("captcha_required", "Please complete the verification challenge.", 400)
    try:
        async with httpx.AsyncClient(timeout=6) as client:
            r = await client.post("https://challenges.cloudflare.com/turnstile/v0/siteverify",
                                  data={"secret": secret, "response": token, "remoteip": client_ip(request) or ""})
            ok = r.json().get("success") is True
    except Exception:  # noqa: BLE001 - fail closed on verification outage
        ok = False
    if not ok:
        raise AppError("captcha_failed", "Verification failed. Please try again.", 400)


def verification_link(user: User) -> str:
    token = create_access_token(user.id, minutes=48 * 60, extra={"typ": "verify", "em": user.email})
    return f"{get_settings().public_web_url}/verify-email?token={token}"


async def _create_user(db, email: str, name: str, password: str | None, *, source: str, request: Request | None,
                       signup_meta: dict | None = None, verified: bool = False) -> User:
    s = get_settings()
    staff = email.lower() in [e.lower() for e in s.admin_emails]
    user = User(email=email.lower(), name=name.strip(), password_hash=hash_password(password) if password else None,
                role="admin" if staff else "teacher", admin_role="super_admin" if staff else None,
                signup_source=source, signup_meta=signup_meta or {}, email_verified=verified,
                email_verified_at=utcnow() if verified else None, referral_code=secrets.token_hex(4),
                password_changed_at=utcnow() if password else None)
    db.add(user)
    await db.flush()
    db.add(TeacherProfile(user_id=user.id))
    await legal.accept(db, user, list(legal.SIGNUP_REQUIRED), request=request, method="signup_checkbox")
    track(db, "signup", user_id=user.id, source=source, **{k: v for k, v in (signup_meta or {}).items() if k.startswith("utm_")})
    await _maybe_start_trial(db, user, request)
    return user


async def _maybe_start_trial(db, user: User, request: Request | None) -> None:
    """One free trial per person: keyed on the normalised email, remembered even after account deletion."""
    from sqlalchemy.dialects.postgresql import insert

    from app.services.usage import start_trial

    if user.role == "admin":
        return
    domain = user.email.split("@")[-1]
    if domain in DISPOSABLE_DOMAINS:
        security_event(db, "trial_abuse", user_id=user.id, request=request, reason="disposable_email")
        return
    res = await db.execute(insert(TrialGrant).values(id=uuid.uuid4(), email_hash=normalised_email_hash(user.email),
                                                     user_id=user.id, created_at=utcnow())
                           .on_conflict_do_nothing(index_elements=["email_hash"]))
    if not res.rowcount:
        security_event(db, "trial_abuse", user_id=user.id, request=request, reason="trial_already_used")
        return
    if await start_trial(db, user):
        track(db, "trial_started", user_id=user.id)


@router.post("/signup", dependencies=[Depends(rate_limit("signup", 30, 3600, by_user=False))])
async def signup(data: SignupIn, request: Request, response: Response, db: DB):
    from app.services.settings import get_setting

    if not (await get_setting("system")).get("registration_enabled", True):
        raise AppError("registration_closed", "New sign-ups are paused right now. Please try again later.", 403)
    if not data.accept_terms:
        raise AppError("terms_required", "Please accept the Terms and Acceptable Use Policy to continue.", 422)
    await verify_captcha(data.captcha_token, request)
    check_password(data.password, data.email)
    exists = (await db.execute(select(User).where(User.email == data.email.lower()))).scalars().first()
    if exists:
        raise AppError("email_taken", "An account with this email already exists. Try signing in.", 409)
    meta = {k: str(v)[:120] for k, v in data.utm.items() if k in ("utm_source", "utm_medium", "utm_campaign",
                                                                   "utm_term", "utm_content", "referrer", "landing")}
    user = await _create_user(db, data.email, data.name, data.password, source="web", request=request, signup_meta=meta)
    if data.referral_code:
        ref = (await db.execute(select(User).where(User.referral_code == data.referral_code))).scalars().first()
        if ref and ref.id != user.id:
            user.referred_by_id = ref.id
    # The marketing choice is recorded either way (unticked by default), separately from the Terms.
    legal.record(db, user.id, "marketing_email", data.marketing_email, request=request, method="signup_checkbox",
                 version="1")
    user.last_login_at = utcnow()
    queue_email(db, user, "verify_email", link=verification_link(user))
    queue_email(db, user, "welcome", link=f"{get_settings().public_web_url}/dashboard")
    _, token = await sessions.start_session(db, user, request, response, method="password")
    security_event(db, "login_success", user_id=user.id, request=request, method="signup")
    await db.commit()
    user = await _load(db, user.id)
    return {"user": user_out(user), "token": token}


def _login_block(user: User) -> AppError | None:
    return {
        "suspended": AppError("account_suspended", "This account is suspended. Contact support.", 403),
        "banned": AppError("account_banned", "This account has been closed for breaking our terms.", 403),
        "pending_deletion": AppError("account_pending_deletion", "This account is scheduled for deletion. Contact "
                                     "support within the grace period to restore it.", 403),
        "deleted": AppError("invalid_credentials", "Email or password is incorrect.", 401),
    }.get(user.status)


@router.post("/login", dependencies=[Depends(rate_limit("login", 60, 300, by_user=False))])
async def login(data: LoginIn, request: Request, response: Response, db: DB):
    # Per account, so password guessing is throttled even when attempts come from many IPs, and one busy
    # school IP doesn't lock out everyone else.
    await enforce(f"login-account:{data.email.lower()}", 10, 300)
    user = (await db.execute(select(User).where(User.email == data.email.lower()))).scalars().first()
    if user is None or not verify_password(data.password, user.password_hash):
        security_event(db, "login_failed", user_id=user.id if user else None, request=request,
                       email_domain=data.email.split("@")[-1])
        await db.commit()
        raise AppError("invalid_credentials", "Email or password is incorrect.", 401)
    if (err := _login_block(user)) is not None:
        security_event(db, "login_failed", user_id=user.id, request=request, reason=user.status)
        await db.commit()
        raise err
    user.last_login_at = utcnow()
    _, token = await sessions.start_session(db, user, request, response, method="password")
    security_event(db, "login_success", user_id=user.id, request=request)
    track(db, "login", user_id=user.id)
    await db.commit()
    user = await _load(db, user.id)
    return {"user": user_out(user), "token": token}


@router.post("/logout")
async def logout(request: Request, response: Response, db: DB):
    """Ends this device's session (if the token is still valid) and clears the cookie."""
    from app.core.deps import _token_from_request

    token = _token_from_request(request)
    data = decode_token(token) if token else None
    if data and data.get("sid"):
        await sessions.revoke(db, uuid.UUID(data["sub"]), session_id=uuid.UUID(data["sid"]), reason="logout")
        await db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.post("/logout-all")
async def logout_all(user: CurrentUser, request: Request, response: Response, db: DB):
    n = await sessions.revoke(db, user.id, reason="logout_all")
    security_event(db, "logout_all", user_id=user.id, request=request, sessions=n)
    await db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True, "revoked": n}


@router.get("/sessions")
async def list_sessions(user: CurrentUser, request: Request, db: DB):
    rows = (await db.execute(select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None),
                                                       UserSession.expires_at > utcnow())
                             .order_by(UserSession.last_active_at.desc()).limit(50))).scalars().all()
    return {"items": [sessions.session_out(s, request.state.session_id) for s in rows]}


@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: uuid.UUID, user: CurrentUser, request: Request, db: DB):
    n = await sessions.revoke(db, user.id, session_id=session_id, reason="user")
    if not n:
        raise AppError("not_found", "Session not found", 404)
    security_event(db, "session_revoked", user_id=user.id, request=request, session_id=str(session_id), by="user")
    await db.commit()
    return {"ok": True}


@router.get("/me")
async def me(user: CurrentUser, db: DB):
    user = await _load(db, user.id)
    pending = await legal.pending_acceptance(db, user)
    return {"user": user_out(user), "pending_legal": [legal.doc_out(d) for d in pending]}


# --------------------------------------------------------------------------- email verification & passwords


class TokenIn(BaseModel):
    token: str = Field(max_length=2000)


@router.post("/verify-email")
async def verify_email(data: TokenIn, request: Request, db: DB):
    payload = decode_token(data.token, typ="verify")
    user = await db.get(User, uuid.UUID(payload["sub"])) if payload else None
    if user is None or payload.get("em") != user.email:
        raise AppError("link_expired", "This link has expired or was already replaced. Request a new one.", 400)
    if not user.email_verified:
        user.email_verified, user.email_verified_at = True, utcnow()
        security_event(db, "email_verified", user_id=user.id, request=request)
        track(db, "verification_completed", user_id=user.id)
        await db.commit()
    return {"ok": True, "email": user.email}


@router.post("/resend-verification", dependencies=[Depends(rate_limit("verify_resend", 3, 3600))])
async def resend_verification(user: CurrentUser, db: DB):
    if user.email_verified:
        return {"ok": True, "already_verified": True}
    queue_email(db, user, "verify_email", link=verification_link(user))
    await db.commit()
    return {"ok": True}


class ForgotIn(BaseModel):
    email: EmailStr
    captcha_token: str | None = None


def _reset_fingerprint(user: User) -> str:
    # The link stops working once the password changes, so each link works once.
    return hashlib.sha256((user.password_hash or "none").encode()).hexdigest()[:16]


def reset_link(user: User) -> str:
    token = create_access_token(user.id, minutes=30, extra={"typ": "reset", "pw": _reset_fingerprint(user)})
    return f"{get_settings().public_web_url}/reset-password?token={token}"


@router.post("/forgot-password", dependencies=[Depends(rate_limit("forgot", 5, 900, by_user=False))])
async def forgot_password(data: ForgotIn, request: Request, db: DB):
    """Always answers the same way, so it can't be used to discover which emails have accounts."""
    await verify_captcha(data.captcha_token, request)
    await enforce(f"forgot-account:{data.email.lower()}", 3, 3600)
    user = (await db.execute(select(User).where(User.email == data.email.lower()))).scalars().first()
    if user and user.status == "active":
        queue_email(db, user, "password_reset", link=reset_link(user))
        security_event(db, "password_reset_requested", user_id=user.id, request=request)
        await db.commit()
    return {"ok": True, "message": "If an account exists for that email, we've sent a reset link."}


class ResetIn(BaseModel):
    token: str = Field(max_length=2000)
    password: str = Field(min_length=8, max_length=200)


@router.post("/reset-password", dependencies=[Depends(rate_limit("reset", 10, 900, by_user=False))])
async def reset_password(data: ResetIn, request: Request, db: DB):
    payload = decode_token(data.token, typ="reset")
    user = await db.get(User, uuid.UUID(payload["sub"])) if payload else None
    if user is None or payload.get("pw") != _reset_fingerprint(user) or user.status != "active":
        raise AppError("link_expired", "This reset link has expired or was already used. Request a new one.", 400)
    check_password(data.password, user.email)
    user.password_hash, user.password_changed_at = hash_password(data.password), utcnow()
    user.email_verified = True  # they proved they control the inbox
    user.email_verified_at = user.email_verified_at or utcnow()
    n = await sessions.revoke(db, user.id, reason="password_change")
    security_event(db, "password_reset", user_id=user.id, request=request, sessions_revoked=n)
    queue_email(db, user, "password_changed", link=f"{get_settings().public_web_url}/forgot-password")
    await db.commit()
    return {"ok": True}


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


@router.post("/change-password", dependencies=[Depends(rate_limit("change_password", 5, 900))])
async def change_password(data: ChangePasswordIn, user: CurrentUser, request: Request, db: DB):
    if not verify_password(data.current_password, user.password_hash):
        security_event(db, "login_failed", user_id=user.id, request=request, reason="change_password_wrong_current")
        await db.commit()
        raise AppError("invalid_credentials", "Your current password is incorrect.", 400)
    check_password(data.new_password, user.email)
    user.password_hash, user.password_changed_at = hash_password(data.new_password), utcnow()
    n = await sessions.revoke(db, user.id, except_id=request.state.session_id, reason="password_change")
    security_event(db, "password_changed", user_id=user.id, request=request, other_sessions_revoked=n)
    queue_email(db, user, "password_changed", link=f"{get_settings().public_web_url}/forgot-password")
    await db.commit()
    return {"ok": True, "other_sessions_revoked": n}


class MagicIn(BaseModel):
    token: str


@router.post("/magic")
async def magic(data: MagicIn, request: Request, response: Response, db: DB):
    """Exchange a short-lived deep-link token (from WhatsApp) for a session."""
    payload = decode_token(data.token, typ="magic")
    if not payload:
        raise AppError("link_expired", "This link has expired. Open the app to sign in.", 401)
    user = await _load(db, uuid.UUID(payload["sub"]))
    if user.status != "active":
        raise HTTPException(status_code=403, detail="Account unavailable")
    await sessions.start_session(db, user, request, response, method="magic")
    await db.commit()
    return {"user": user_out(user), "redirect": payload.get("r", "/dashboard")}


# --------------------------------------------------------------------------- OAuth (Google / Microsoft)

OAUTH = {
    "google": {"auth": "https://accounts.google.com/o/oauth2/v2/auth", "token": "https://oauth2.googleapis.com/token",
               "userinfo": "https://openidconnect.googleapis.com/v1/userinfo", "scope": "openid email profile"},
    "microsoft": {"auth": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
                  "token": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                  "userinfo": "https://graph.microsoft.com/oidc/userinfo", "scope": "openid email profile User.Read"},
}


def _oauth_creds(provider: str) -> tuple[str, str]:
    s = get_settings()
    cid = getattr(s, f"{provider}_client_id", None)
    secret = getattr(s, f"{provider}_client_secret", None)
    if provider not in OAUTH or not cid or not secret:
        raise AppError("oauth_not_configured", f"{provider.title()} sign-in is not configured.", 404)
    return cid, secret


@router.get("/oauth/providers")
async def oauth_providers():
    s = get_settings()
    return {"providers": [p for p in OAUTH if getattr(s, f"{p}_client_id", None)]}


@router.get("/oauth/{provider}/start")
async def oauth_start(provider: str):
    cid, _ = _oauth_creds(provider)
    s = get_settings()
    state = secrets.token_urlsafe(24)
    params = {"client_id": cid, "response_type": "code", "scope": OAUTH[provider]["scope"], "state": state,
              "redirect_uri": f"{s.public_web_url}/api/v1/auth/oauth/{provider}/callback", "prompt": "select_account"}
    resp = RedirectResponse(f"{OAUTH[provider]['auth']}?{urlencode(params)}")
    resp.set_cookie("oauth_state", state, httponly=True, secure=s.cookie_secure, samesite="lax", max_age=600)
    return resp


@router.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, request: Request, db: DB, code: str = "", state: str = ""):
    cid, secret = _oauth_creds(provider)
    s = get_settings()
    if not state or state != request.cookies.get("oauth_state"):
        raise AppError("oauth_state", "Sign-in expired. Please try again.", 400)
    async with httpx.AsyncClient(timeout=15) as client:
        tok = await client.post(OAUTH[provider]["token"], data={
            "client_id": cid, "client_secret": secret, "code": code, "grant_type": "authorization_code",
            "redirect_uri": f"{s.public_web_url}/api/v1/auth/oauth/{provider}/callback"})
        if tok.status_code != 200:
            raise AppError("oauth_failed", "Could not complete sign-in.", 400)
        info = (await client.get(OAUTH[provider]["userinfo"],
                                 headers={"Authorization": f"Bearer {tok.json()['access_token']}"})).json()
    email = (info.get("email") or info.get("preferred_username") or "").lower()
    subject = info.get("sub")
    if not email or not subject:
        raise AppError("oauth_failed", "Your account did not share an email address.", 400)
    link = (await db.execute(select(OAuthAccount).where(OAuthAccount.provider == provider,
                                                          OAuthAccount.subject == subject))).scalars().first()
    verified = info.get("email_verified") in (True, "true") or provider == "microsoft"
    if link:
        user = await db.get(User, link.user_id)
    else:
        if not verified:
            # Never attach a sign-in to an existing account on an unverified email claim.
            raise AppError("oauth_unverified", "Your provider hasn't verified this email address.", 400)
        user = (await db.execute(select(User).where(User.email == email))).scalars().first()
        if user is None:
            user = await _create_user(db, email, info.get("name") or email.split("@")[0], None, source=provider,
                                      request=request, verified=True)
        user.email_verified = True
        user.email_verified_at = user.email_verified_at or utcnow()
        db.add(OAuthAccount(user_id=user.id, provider=provider, subject=subject))
    if (err := _login_block(user)) is not None:
        raise err
    user.last_login_at = utcnow()
    resp = RedirectResponse(f"{s.public_web_url}/dashboard")
    await sessions.start_session(db, user, request, resp, method=provider)
    security_event(db, "login_success", user_id=user.id, request=request, method=provider)
    await db.commit()
    resp.delete_cookie("oauth_state")
    return resp
