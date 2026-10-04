"""Signed first-party browser cookie. A deterrent, not a claim to identify a physical device."""
import hashlib
import hmac
import re
import secrets

from fastapi import Request, Response
from sqlalchemy import text

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.rewards import TrialDeviceException, TrialDeviceGrant

COOKIE = "clastio_installation"
MAX_AGE = 365 * 24 * 60 * 60


def _signature(token: str) -> str:
    return hmac.new(get_settings().secret_key.encode(), f"installation:{token}".encode(), hashlib.sha256).hexdigest()


def cookie_digest(value: str | None) -> str | None:
    if not value or len(value) != 108:
        return None
    token, _, signature = value.partition(".")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token) or not hmac.compare_digest(signature, _signature(token)):
        return None
    return hashlib.sha256(token.encode()).hexdigest()


def ensure_cookie(request: Request, response: Response, *, strict: bool = False) -> str | None:
    value = request.cookies.get(COOKIE)
    digest = cookie_digest(value)
    if digest:
        return digest
    if value is not None:
        if strict:
            raise AppError("browser_verification_failed", "Browser verification failed. Contact support for help with trial or reward eligibility.", 403)
        # Sign-in and Free access remain available, but never silently replace
        # a present invalid signature with an eligible fresh browser identity.
        return None
    token = secrets.token_urlsafe(32)
    response.set_cookie(COOKIE, f"{token}.{_signature(token)}", max_age=MAX_AGE,
                        httponly=True, secure=get_settings().cookie_secure, samesite="lax", path="/api/v1")
    return hashlib.sha256(token.encode()).hexdigest()


async def device_used(db, user_id, digest: str | None) -> bool:
    if not digest or await db.get(TrialDeviceException, user_id):
        return False
    return await db.get(TrialDeviceGrant, digest) is not None


async def claim_device(db, user_id, digest: str | None) -> bool:
    if not digest or await db.get(TrialDeviceException, user_id):
        return True
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                     {"key": f"trial-device:{digest}"})
    if await db.get(TrialDeviceGrant, digest):
        return False
    db.add(TrialDeviceGrant(device_hash=digest, user_id=user_id))
    return True
