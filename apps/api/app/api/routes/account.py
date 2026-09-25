"""Teacher-facing account features: legal documents and consent, notifications, announcements and support."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, text, update

from app.core.db import utcnow
from app.core.deps import DB, CurrentUser
from app.core.errors import AppError, NotFound
from app.core.logging import request_id_var
from app.core.pagination import clamp, keyset, page
from app.core.ratelimit import rate_limit
from app.models import Announcement, LegalDocument, Notification, SupportTicket, TicketMessage, User
from app.services import legal
from app.services.events import track

router = APIRouter()


# --------------------------------------------------------------------------- legal (public)


@router.get("/legal", tags=["legal"])
async def legal_index(db: DB):
    """The current version of every published policy."""
    return {"items": [legal.doc_out(d) for d in (await legal.current_all(db)).values()]}


@router.get("/legal/{doc_type}", tags=["legal"])
async def legal_document(doc_type: str, db: DB, version: str | None = None):
    if doc_type not in legal.DOC_TYPES:
        raise NotFound("Document")
    if version:
        doc = (await db.execute(select(LegalDocument).where(
            LegalDocument.document_type == doc_type, LegalDocument.version == version,
            LegalDocument.status.in_(("published", "archived"))))).scalars().first()
    else:
        doc = await legal.current(db, doc_type)
    if doc is None:
        raise NotFound("Document")
    history = (await db.execute(select(LegalDocument).where(
        LegalDocument.document_type == doc_type, LegalDocument.status.in_(("published", "archived")))
        .order_by(LegalDocument.published_at.desc()))).scalars().all()
    return {**legal.doc_out(doc, content=True), "versions": [legal.doc_out(d) for d in history]}


# --------------------------------------------------------------------------- consent


class AcceptIn(BaseModel):
    document_types: list[str] = Field(min_length=1, max_length=10)


@router.post("/me/legal/accept", tags=["legal"])
async def accept_documents(data: AcceptIn, user: CurrentUser, request: Request, db: DB):
    """Accept the current version of updated policies (the "we've updated our terms" prompt)."""
    bad = [t for t in data.document_types if t not in legal.DOC_TYPES]
    if bad:
        raise AppError("bad_request", f"Unknown document: {', '.join(bad)}", 400)
    rows = await legal.accept(db, user, data.document_types, request=request, method="reacceptance_modal")
    await db.commit()
    return {"accepted": [{"kind": c.kind, "version": c.version} for c in rows],
            "pending": [legal.doc_out(d) for d in await legal.pending_acceptance(db, user)]}


@router.get("/me/consents", tags=["legal"])
async def my_consents(user: CurrentUser, db: DB):
    latest = await legal.latest_consents(db, user.id)
    return {"consents": latest,
            "marketing": {k: bool(latest.get(k, {}).get("granted")) for k in legal.MARKETING},
            "cookies": {k: bool(latest.get(f"cookie_{k}", {}).get("granted")) for k in ("analytics", "marketing")}}


class MarketingIn(BaseModel):
    marketing_email: bool | None = None
    marketing_sms: bool | None = None
    marketing_whatsapp: bool | None = None


@router.put("/me/consents", tags=["legal"])
async def update_consents(data: MarketingIn, user: CurrentUser, request: Request, db: DB):
    """Opt in or out of each marketing channel. Only changes are recorded; history is kept."""
    latest = await legal.latest_consents(db, user.id)
    for kind, value in data.model_dump(exclude_none=True).items():
        if bool(latest.get(kind, {}).get("granted")) != value:
            legal.record(db, user.id, kind, value, request=request, method="settings", version="1")
    await db.commit()
    return await my_consents(user, db)


class CookieIn(BaseModel):
    analytics: bool = False
    marketing: bool = False


@router.post("/me/cookie-consent", tags=["legal"])
async def cookie_consent(data: CookieIn, user: CurrentUser, request: Request, db: DB):
    """Record a signed-in visitor's cookie choice (essential cookies need no consent)."""
    doc = await legal.current(db, "cookie")
    latest = await legal.latest_consents(db, user.id)
    for k, v in (("analytics", data.analytics), ("marketing", data.marketing)):
        kind = f"cookie_{k}"
        if kind not in latest or latest[kind]["granted"] != v:
            legal.record(db, user.id, kind, v, request=request, method="banner", version=doc.version if doc else "1")
    await db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- notifications


@router.get("/me/notifications", tags=["notifications"])
async def notifications(user: CurrentUser, db: DB, cursor: str | None = None, limit: int = 20,
                        unread: bool = False):
    q = select(Notification).where(Notification.user_id == user.id)
    if unread:
        q = q.where(Notification.read_at.is_(None))
    limit = clamp(limit, 20)
    rows, nxt = page(list((await db.execute(keyset(q, Notification, cursor, limit))).scalars().all()), limit)
    count = (await db.execute(select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None)))).scalar_one()
    return {"items": [{"id": str(n.id), "type": n.type, "title": n.title, "body": n.body, "link": n.link,
                       "read": n.read_at is not None, "created_at": n.created_at.isoformat()} for n in rows],
            "unread": count, "next_cursor": nxt}


class ReadIn(BaseModel):
    ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    all: bool = False


@router.post("/me/notifications/read", tags=["notifications"])
async def mark_read(data: ReadIn, user: CurrentUser, db: DB):
    q = update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    if not data.all:
        if not data.ids:
            return {"updated": 0}
        q = q.where(Notification.id.in_(data.ids))  # scoped to this user above: no IDOR
    res = await db.execute(q.values(read_at=utcnow()))
    await db.commit()
    return {"updated": res.rowcount or 0}


# --------------------------------------------------------------------------- announcements


def announcement_out(a: Announcement) -> dict[str, Any]:
    return {"id": str(a.id), "kind": a.kind, "title": a.title, "body": a.body, "link": a.link,
            "audience": a.audience, "active": a.active, "starts_at": a.starts_at.isoformat(),
            "ends_at": a.ends_at.isoformat() if a.ends_at else None, "created_at": a.created_at.isoformat()}


@router.get("/announcements", tags=["notifications"])
async def active_announcements(user: CurrentUser, db: DB):
    now = utcnow()
    audiences = ("everyone", "staff") if user.role == "admin" else ("everyone", "teachers")
    rows = (await db.execute(select(Announcement).where(
        Announcement.active.is_(True), Announcement.starts_at <= now, Announcement.audience.in_(audiences),
        or_(Announcement.ends_at.is_(None), Announcement.ends_at > now))
        .order_by(Announcement.starts_at.desc()).limit(5))).scalars().all()
    return {"items": [announcement_out(a) for a in rows]}


# --------------------------------------------------------------------------- support


TICKET_KINDS = ("support", "bug", "billing", "feature_request")


def ticket_out(t: SupportTicket, *, email: str | None = None) -> dict[str, Any]:
    out = {"id": str(t.id), "number": t.number, "kind": t.kind, "subject": t.subject, "status": t.status,
           "priority": t.priority, "category": t.category, "created_at": t.created_at.isoformat(),
           "updated_at": t.updated_at.isoformat(), "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None}
    if email is not None:
        out["email"] = email
    return out


def message_out(m: TicketMessage, author: User | None, *, staff_view: bool) -> dict[str, Any]:
    is_staff = bool(author and author.role == "admin")
    return {"id": str(m.id), "body": m.body, "internal": m.internal, "created_at": m.created_at.isoformat(),
            "from_staff": is_staff,
            # Teachers see "PPT Genie support", never the staff member's personal details.
            "author": (author.email if staff_view and author else ("PPT Genie support" if is_staff else "You"))}


class TicketIn(BaseModel):
    kind: str = Field("support", pattern="^(support|bug|billing|feature_request)$")
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=5, max_length=10_000)
    category: str | None = Field(None, max_length=60)


async def next_ticket_number(db) -> int:
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('support_ticket_number'))"))
    return int((await db.execute(select(func.coalesce(func.max(SupportTicket.number), 1000)))).scalar_one()) + 1


@router.post("/support/tickets", tags=["support"], dependencies=[Depends(rate_limit("ticket", 10, 3600))])
async def create_ticket(data: TicketIn, user: CurrentUser, db: DB):
    t = SupportTicket(number=await next_ticket_number(db), user_id=user.id, kind=data.kind,
                      subject=data.subject.strip(), category=data.category,
                      priority="high" if data.kind == "billing" else "normal", request_id=request_id_var.get())
    db.add(t)
    await db.flush()
    db.add(TicketMessage(ticket_id=t.id, author_id=user.id, body=data.body.strip()))
    track(db, "ticket_created", user_id=user.id, kind=data.kind)
    await db.commit()
    return ticket_out(t)


@router.get("/support/tickets", tags=["support"])
async def my_tickets(user: CurrentUser, db: DB, kind: str | None = None):
    q = select(SupportTicket).where(SupportTicket.user_id == user.id)
    if kind:
        q = q.where(SupportTicket.kind == kind)
    rows = (await db.execute(q.order_by(SupportTicket.updated_at.desc()).limit(100))).scalars().all()
    return {"items": [ticket_out(t) for t in rows]}


async def _my_ticket(db, user: User, ticket_id: uuid.UUID) -> SupportTicket:
    t = await db.get(SupportTicket, ticket_id)
    if t is None or t.user_id != user.id:  # someone else's ticket looks exactly like a missing one
        raise NotFound("Ticket")
    return t


@router.get("/support/tickets/{ticket_id}", tags=["support"])
async def my_ticket(ticket_id: uuid.UUID, user: CurrentUser, db: DB):
    t = await _my_ticket(db, user, ticket_id)
    rows = (await db.execute(select(TicketMessage, User).outerjoin(User, User.id == TicketMessage.author_id)
                             .where(TicketMessage.ticket_id == t.id, TicketMessage.internal.is_(False))
                             .order_by(TicketMessage.created_at))).all()
    return {**ticket_out(t), "messages": [message_out(m, a, staff_view=False) for m, a in rows]}


class ReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)


@router.post("/support/tickets/{ticket_id}/messages", tags=["support"],
             dependencies=[Depends(rate_limit("ticket_reply", 60, 3600))])
async def reply_ticket(ticket_id: uuid.UUID, data: ReplyIn, user: CurrentUser, db: DB):
    t = await _my_ticket(db, user, ticket_id)
    if t.status == "closed":
        raise AppError("ticket_closed", "This request is closed. Open a new one if you still need help.", 409)
    db.add(TicketMessage(ticket_id=t.id, author_id=user.id, body=data.body.strip()))
    if t.status in ("pending", "resolved"):
        t.status = "open"
    t.updated_at = utcnow()
    await db.commit()
    return {"ok": True}
