from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import uuid
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings
from app.core.db import utcnow

_hasher = PasswordHasher()
COOKIE_NAME = "ata_session"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: uuid.UUID, *, minutes: int | None = None, extra: dict | None = None) -> str:
    settings = get_settings()
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes or settings.access_token_minutes)).timestamp()),
        "typ": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str, typ: str = "access") -> dict | None:
    try:
        data = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if data.get("typ") != typ:
        return None
    return data


def create_magic_token(user_id: uuid.UUID, redirect: str, minutes: int = 30) -> str:
    """Short-lived deep-link token (used in WhatsApp links)."""
    return create_access_token(user_id, minutes=minutes, extra={"typ": "magic", "r": redirect})


def sign_value(value: str, expires_at: int | None = None) -> str:
    """HMAC signature for signed download URLs served by the API (local storage backend)."""
    msg = f"{value}:{expires_at or ''}".encode()
    return hmac.new(get_settings().secret_key.encode(), msg, hashlib.sha256).hexdigest()


def verify_signed_value(value: str, expires_at: int, signature: str) -> bool:
    if expires_at < int(time.time()):
        return False
    return hmac.compare_digest(sign_value(value, expires_at), signature)


def random_code(n: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(n))
