from __future__ import annotations

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
from app.core.ratelimit import rate_limit
from app.core.security import (
    COOKIE_NAME,
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import AuditLog, Consent, OAuthAccount, TeacherProfile, User

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    accept_terms: bool = True


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def user_out(u: User) -> dict[str, Any]:
    return {"id": str(u.id), "email": u.email, "name": u.name, "role": u.role, "locale": u.locale,
            "timezone": u.timezone, "onboarding_completed": bool(u.profile and u.profile.onboarding_completed)}


def set_session(response: Response, user: User) -> str:
    s = get_settings()
    token = create_access_token(user.id)
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=s.cookie_secure, samesite="lax",
                        max_age=s.access_token_minutes * 60, path="/")
    return token


async def _load(db, user_id: uuid.UUID) -> User:
    from sqlalchemy.orm import selectinload

    return (await db.execute(select(User).options(selectinload(User.profile)).where(User.id == user_id))
            ).scalars().one()


async def _create_user(db, email: str, name: str, password: str | None) -> User:
    s = get_settings()
    user = User(email=email.lower(), name=name.strip(), password_hash=hash_password(password) if password else None,
                role="admin" if email.lower() in [e.lower() for e in s.admin_emails] else "teacher")
    db.add(user)
    await db.flush()
    db.add(TeacherProfile(user_id=user.id))
    db.add(Consent(user_id=user.id, kind="terms", granted=True))
    db.add(Consent(user_id=user.id, kind="privacy", granted=True))
    return user


@router.post("/signup", dependencies=[Depends(rate_limit("signup", 5, 300, by_user=False))])
async def signup(data: SignupIn, response: Response, db: DB):
    if not data.accept_terms:
        raise AppError("terms_required", "Please accept the terms to continue.", 400)
    exists = (await db.execute(select(User).where(User.email == data.email.lower()))).scalars().first()
    if exists:
        raise AppError("email_taken", "An account with this email already exists. Try signing in.", 409)
    user = await _create_user(db, data.email, data.name, data.password)
    user.last_login_at = utcnow()
    await db.commit()
    user = await _load(db, user.id)
    token = set_session(response, user)
    return {"user": user_out(user), "token": token}


@router.post("/login", dependencies=[Depends(rate_limit("login", 10, 300, by_user=False))])
async def login(data: LoginIn, request: Request, response: Response, db: DB):
    user = (await db.execute(select(User).where(User.email == data.email.lower()))).scalars().first()
    if user is None or not verify_password(data.password, user.password_hash):
        raise AppError("invalid_credentials", "Email or password is incorrect.", 401)
    if user.status != "active":
        raise AppError("account_suspended", "This account is suspended. Contact support.", 403)
    user.last_login_at = utcnow()
    db.add(AuditLog(actor_id=user.id, action="login", ip=request.client.host if request.client else None))
    await db.commit()
    user = await _load(db, user.id)
    token = set_session(response, user)
    return {"user": user_out(user), "token": token}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: CurrentUser, db: DB):
    user = await _load(db, user.id)
    return {"user": user_out(user)}


class MagicIn(BaseModel):
    token: str


@router.post("/magic")
async def magic(data: MagicIn, response: Response, db: DB):
    """Exchange a short-lived deep-link token (from WhatsApp) for a session."""
    payload = decode_token(data.token, typ="magic")
    if not payload:
        raise AppError("link_expired", "This link has expired. Open the app to sign in.", 401)
    user = await _load(db, uuid.UUID(payload["sub"]))
    if user.status != "active":
        raise HTTPException(status_code=403, detail="Account unavailable")
    set_session(response, user)
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
              "redirect_uri": f"{s.public_api_url}/api/v1/auth/oauth/{provider}/callback", "prompt": "select_account"}
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
            "redirect_uri": f"{s.public_api_url}/api/v1/auth/oauth/{provider}/callback"})
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
    if link:
        user = await db.get(User, link.user_id)
    else:
        user = (await db.execute(select(User).where(User.email == email))).scalars().first()
        if user is None:
            user = await _create_user(db, email, info.get("name") or email.split("@")[0], None)
        user.email_verified = True
        db.add(OAuthAccount(user_id=user.id, provider=provider, subject=subject))
    user.last_login_at = utcnow()
    await db.commit()
    resp = RedirectResponse(f"{s.public_web_url}/dashboard")
    set_session(resp, user)
    resp.delete_cookie("oauth_state")
    return resp
