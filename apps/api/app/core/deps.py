from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.logging import user_id_var
from app.core.security import COOKIE_NAME, decode_token
from app.models import User

DB = Annotated[AsyncSession, Depends(get_db)]


def _token_from_request(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(COOKIE_NAME)


async def get_current_user(request: Request, db: DB) -> User:
    token = _token_from_request(request)
    data = decode_token(token) if token else None
    if not data:
        raise HTTPException(status_code=401, detail="Not signed in")
    user = await db.get(User, uuid.UUID(data["sub"]))
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="Account unavailable")
    request.state.user_id = user.id
    user_id_var.set(str(user.id))
    return user


async def get_admin_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(get_admin_user)]
