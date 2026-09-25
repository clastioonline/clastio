"""Keyset (cursor) pagination for large, append-heavy tables.

Rows are ordered newest first by (created_at, id). The cursor is the position of the last row returned, so new rows
arriving between pages never shift or duplicate results the way OFFSET does.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, or_

from app.core.errors import AppError

MAX_LIMIT = 200


def encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    raw = json.dumps([created_at.isoformat(), str(row_id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        at, rid = json.loads(raw)
        return datetime.fromisoformat(at), uuid.UUID(rid)
    except (ValueError, TypeError) as e:
        raise AppError("invalid_cursor", "The page cursor is not valid. Start from the first page.", 400) from e


def clamp(limit: int | None, default: int = 50) -> int:
    return max(1, min(limit or default, MAX_LIMIT))


def keyset(query: Select, model: Any, cursor: str | None, limit: int) -> Select:
    """Apply newest-first keyset ordering. Fetches limit + 1 rows so the caller can tell if there is a next page."""
    if cursor:
        at, rid = decode_cursor(cursor)
        query = query.where(or_(model.created_at < at, and_(model.created_at == at, model.id < rid)))
    return query.order_by(model.created_at.desc(), model.id.desc()).limit(limit + 1)


def page(rows: list[Any], limit: int, key=lambda r: r) -> tuple[list[Any], str | None]:
    """Trim the extra row and build the next cursor from the last row kept."""
    more = len(rows) > limit
    rows = rows[:limit]
    nxt = None
    if more and rows:
        last = key(rows[-1])
        nxt = encode_cursor(last.created_at, last.id)
    return rows, nxt
