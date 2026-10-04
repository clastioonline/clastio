from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db, utcnow
from app.core.logging import user_id_var
from app.core.permissions import permissions_for
from app.core.security import COOKIE_NAME, decode_token
from app.models import User

DB = Annotated[AsyncSession, Depends(get_db)]

# Statuses that may still use the API. Everything else (suspended, banned, pending_deletion, deleted) is refused.
USABLE_STATUSES = {"active"}


def _token_from_request(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(COOKIE_NAME)


async def get_current_user(request: Request, db: DB) -> User:
    from app.services import sessions

    token = _token_from_request(request)
    data = decode_token(token) if token else None
    if not data:
        raise HTTPException(status_code=401, detail="Not signed in")
    user = await db.get(User, uuid.UUID(data["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    sess = await sessions.load_active(db, data.get("sid"), user.id)
    if sess is None:
        raise HTTPException(status_code=401, detail="Your session has ended. Please sign in again.")
    if user.status not in USABLE_STATUSES:
        raise HTTPException(status_code=403, detail="This account is not available. Contact support.")
    from app.core.config import get_settings
    checked = getattr(user, "clerk_checked_at", None)
    refresh_clerk = (user.role == "admin" or request.url.path == "/api/v1/auth/me"
                     or checked is None or utcnow() - checked >= timedelta(seconds=60))
    if get_settings().clerk_secret_key and refresh_clerk:
        if user.role == "admin" and sess.method != "clerk":
            raise HTTPException(status_code=403, detail="Sign in through Clerk for admin access")
        # Refresh roles when loading the current account, including promotions,
        # and recheck privileged sessions before granting admin access.
        import httpx
        from sqlalchemy import select

        from app.models import OAuthAccount
        from app.services.clerk_roles import apply_clerk_role
        identity = (await db.execute(select(OAuthAccount).where(
            OAuthAccount.user_id == user.id, OAuthAccount.provider == "clerk"))).scalars().first()
        if identity is None and user.role == "admin":
            raise HTTPException(status_code=403, detail="Sign in through Clerk for admin access")
        if identity is not None:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    result = await client.get(f"https://api.clerk.com/v1/users/{identity.subject}",
                        headers={"Authorization": f"Bearer {get_settings().clerk_secret_key}"})
            except httpx.HTTPError:
                raise HTTPException(status_code=503, detail="Could not verify your Clerk account") from None
            if result.status_code == 404:
                await sessions.revoke(db, user.id, reason="clerk_deleted")
                await db.commit()
                raise HTTPException(status_code=403, detail="Clerk account unavailable")
            if not result.is_success:
                raise HTTPException(status_code=503, detail="Could not verify your Clerk account")
            info = result.json()
            if info.get("banned"):
                await sessions.revoke(db, user.id, reason="clerk_banned")
                await db.commit()
                raise HTTPException(status_code=403, detail="Clerk account unavailable")
            apply_clerk_role(user, info)
            user.clerk_checked_at = utcnow()
            # Persist account status verification at most once per minute for
            # teachers; staff and account refresh always check Clerk directly.
            await db.commit()
            if user.role == "admin" and sess.method != "clerk":
                raise HTTPException(status_code=403, detail="Sign in through Clerk for admin access")
        else:
            user.clerk_checked_at = utcnow()
            await db.commit()
    request.state.user_id = user.id
    request.state.session_id = sess.id
    user_id_var.set(str(user.id))
    await sessions.touch(db, sess, user)
    return user


def staff_permissions(user: User) -> set[str]:
    return permissions_for(user.role, user.admin_role)


def can_access(user: User, owner_id) -> bool:
    """Owners reach their own resources; staff only with the users.content permission."""
    return owner_id == user.id or "users.content" in staff_permissions(user)


async def get_admin_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not staff_permissions(user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require(*perms: str):
    """Dependency: the signed-in staff member must hold every listed permission."""

    async def dep(user: Annotated[User, Depends(get_current_user)]) -> User:
        granted = staff_permissions(user)
        if not granted:
            raise HTTPException(status_code=403, detail="Admin access required")
        missing = [p for p in perms if p not in granted]
        if missing:
            raise HTTPException(status_code=403, detail=f"Your role doesn't allow this ({', '.join(missing)}).")
        return user

    return dep


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(get_admin_user)]
