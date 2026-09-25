"""Versioned legal documents and consent records.

Each published version is its own row; nothing is overwritten. Accepting a document appends a consent record with
the exact version, time, IP, user agent and method. Terms, Privacy, Acceptable Use and each marketing channel are
separate consents. When a new version marked `requires_acceptance` is published, signed-in users must accept it.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import utcnow
from app.core.request_meta import client_ip, user_agent
from app.models import Consent, LegalDocument, User

DOC_TYPES = {"terms": "Terms & Conditions", "privacy": "Privacy Policy", "acceptable_use": "Acceptable Use Policy",
             "cookie": "Cookie Policy", "refund": "Refund Policy", "dmca": "Copyright (DMCA) Policy"}
SIGNUP_REQUIRED = ("terms", "privacy", "acceptable_use")
MARKETING = ("marketing_email", "marketing_sms", "marketing_whatsapp")


async def current(db: AsyncSession, doc_type: str) -> LegalDocument | None:
    return (await db.execute(select(LegalDocument).where(
        LegalDocument.document_type == doc_type, LegalDocument.status == "published",
        (LegalDocument.effective_from.is_(None)) | (LegalDocument.effective_from <= utcnow()))
        .order_by(LegalDocument.published_at.desc()).limit(1))).scalars().first()


async def current_all(db: AsyncSession) -> dict[str, LegalDocument]:
    out = {}
    for t in DOC_TYPES:
        doc = await current(db, t)
        if doc:
            out[t] = doc
    return out


def doc_out(d: LegalDocument, *, content: bool = False) -> dict[str, Any]:
    out = {"id": str(d.id), "type": d.document_type, "title": d.title, "version": d.version, "status": d.status,
           "requires_acceptance": d.requires_acceptance, "summary_of_changes": d.summary_of_changes,
           "effective_from": d.effective_from.isoformat() if d.effective_from else None,
           "published_at": d.published_at.isoformat() if d.published_at else None}
    if content:
        out["content"] = d.content
    return out


def record(db: AsyncSession, user_id: uuid.UUID, kind: str, granted: bool, *, request: Request | None,
           method: str, doc: LegalDocument | None = None, version: str | None = None, source: str | None = None) -> Consent:
    c = Consent(user_id=user_id, kind=kind, granted=granted, version=(doc.version if doc else version or "1"),
                document_id=doc.id if doc else None, method=method, source=source, ip=client_ip(request),
                user_agent=user_agent(request))
    db.add(c)
    return c


async def accept(db: AsyncSession, user: User, doc_types: list[str], *, request: Request | None, method: str) -> list[Consent]:
    rows = []
    for t in doc_types:
        doc = await current(db, t)
        if doc is None:
            continue
        rows.append(record(db, user.id, t, True, request=request, method=method, doc=doc))
    return rows


async def pending_acceptance(db: AsyncSession, user: User) -> list[LegalDocument]:
    """Current documents that require acceptance and this user hasn't accepted in that exact version."""
    pending = []
    for doc in (await current_all(db)).values():
        if not doc.requires_acceptance:
            continue
        accepted = (await db.execute(select(Consent.id).where(
            Consent.user_id == user.id, Consent.kind == doc.document_type, Consent.granted.is_(True),
            Consent.version == doc.version).limit(1))).first()
        if not accepted:
            pending.append(doc)
    return pending


async def latest_consents(db: AsyncSession, user_id: uuid.UUID) -> dict[str, dict[str, Any]]:
    """The most recent record per kind (history stays in the table)."""
    sub = select(Consent.kind, func.max(Consent.created_at).label("at")).where(Consent.user_id == user_id) \
        .group_by(Consent.kind).subquery()
    rows = (await db.execute(select(Consent).join(sub, and_(Consent.kind == sub.c.kind, Consent.created_at == sub.c.at))
                             .where(Consent.user_id == user_id))).scalars().all()
    return {c.kind: {"granted": c.granted, "version": c.version, "at": c.created_at.isoformat(), "method": c.method}
            for c in rows}


# --------------------------------------------------------------------------- default documents

_NOTICE = ("> **Template — requires review by a qualified lawyer before launch.** This text describes how PPT Genie "
           "actually works so it is a useful starting point, but it is not legal advice and has not been reviewed for "
           "UAE, India or any other jurisdiction.\n\n")

DEFAULT_DOCUMENTS: dict[str, tuple[str, str]] = {
    "terms": ("Terms & Conditions", _NOTICE + """## 1. The service
PPT Genie helps teachers plan lessons and create presentations, documents and media using AI. You need an account, and
you must be at least 18 and a teacher or education professional to use it.

## 2. Your account
Keep your password secret. You are responsible for activity on your account. Tell us at once if you think it has been
compromised.

## 3. Plans, trials and payment
Paid plans renew automatically until cancelled. Prices are shown in the app before you pay. A free trial, where
offered, needs no card and ends automatically. Payments are processed by our payment partner; we never see or store
your card details. Cancelling keeps your plan until the end of the period you paid for.

## 4. Your content
You keep ownership of the files you upload and the lessons you create. You give us permission to process them only
to provide the service to you. You confirm you have the right to upload what you upload.

## 5. AI-generated content
Output is produced by AI and can contain mistakes. Review everything before using it with students. AI-generated
images and videos are labelled as such and must not be presented as made by a person.

## 6. Acceptable use
You must follow the Acceptable Use Policy.

## 7. Suspension and termination
We may suspend or close accounts that break these terms. You can delete your account at any time from Settings.

## 8. Liability
The service is provided "as is". To the extent the law allows, our liability is limited to the amount you paid in the
12 months before the claim.

## 9. Changes
We will tell you about material changes and ask you to accept them before you continue.
"""),
    "privacy": ("Privacy Policy", _NOTICE + """## What we collect
- **Account:** name, email, password hash (never the password), school and teaching preferences you enter.
- **Content:** files you upload and what you create. We use it only to provide the service.
- **Usage:** which features you use, credits consumed, AI model and token counts per generation, request logs
  (without request bodies), sign-in sessions (IP address, browser and operating system).
- **Payments:** handled by our payment partner. We keep the plan, amounts and invoice references, never card data.

## What we don't collect
We don't need student personal data. Don't upload it.

## AI providers
Your prompts and files are sent to AI providers (Anthropic, OpenAI, Google) to generate content. They process it on
our behalf and do not use it to train models under our agreements.

## How long we keep data
Request logs: 90 days. Security events: 1 year. Audit and consent records: as long as legally required. Deleted
accounts: content removed after a 30-day grace period; billing records kept for accounting law.

## Your rights
You can export your data and delete your account from Settings, and withdraw marketing consent at any time.

## Contact
privacy@pptgenie.example (replace with your real contact).
"""),
    "acceptable_use": ("Acceptable Use Policy", _NOTICE + """You must not use PPT Genie to:
- upload personal data about students or anyone else without a lawful basis;
- create content that is illegal, hateful, harassing, sexual involving minors, or that promotes violence;
- create deceptive media of real people, or remove or hide the AI-generated label or provenance data from output;
- infringe copyright, or upload material you don't have the right to use;
- probe, overload or attack the service, share accounts, or resell access without permission;
- get around usage limits, trials or payments.

We may remove content and suspend accounts that break this policy.
"""),
    "cookie": ("Cookie Policy", _NOTICE + """We use only **essential cookies**: your session cookie (keeps you signed
in) and a small preference cookie for your cookie choices. We do not use advertising cookies. If we add analytics or
marketing cookies, they will only load after you agree to them in the cookie banner.
"""),
    "refund": ("Refund Policy", _NOTICE + """Monthly plans can be cancelled at any time and are not refunded for the
current month. Annual plans can be refunded pro rata within 14 days of purchase. Unused media credit packs can be
refunded within 14 days if none of the credits were used. Contact support to request a refund.
"""),
}


async def seed_documents(db: AsyncSession) -> int:
    """Publish v1.0 of each default document if that type has no published version yet."""
    added = 0
    for t, (title, content) in DEFAULT_DOCUMENTS.items():
        if await current(db, t) is None:
            now = utcnow()
            db.add(LegalDocument(document_type=t, version="1.0", title=title, content=content, status="published",
                                 requires_acceptance=t in SIGNUP_REQUIRED, effective_from=now, published_at=now))
            added += 1
    await db.flush()
    return added
