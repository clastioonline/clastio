"""Platform tables: sessions, security, legal, notifications, email, analytics, API requests, idempotency,
support, announcements and admin notes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, utcnow, uuid7


def pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)


def user_fk(nullable: bool = False, ondelete: str = "CASCADE", index: bool = True):
    return mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete=ondelete), nullable=nullable, index=index)


def created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class UserSession(Base):
    """One signed-in device. The session id is inside the access token, so revoking it signs that device out."""

    __tablename__ = "user_sessions"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    created_at: Mapped[datetime] = created()
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    browser: Mapped[str | None] = mapped_column(String(60))
    os: Mapped[str | None] = mapped_column(String(60))
    device_type: Mapped[str | None] = mapped_column(String(20))  # desktop | mobile | tablet | bot | unknown
    method: Mapped[str] = mapped_column(String(20), default="password")  # password | google | microsoft | magic
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(60))  # logout | logout_all | user | admin | password_change


class SecurityEvent(Base):
    __tablename__ = "security_events"
    __table_args__ = (Index("ix_security_type_created", "type", "created_at"),)
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID | None] = user_fk(nullable=True, ondelete="SET NULL")
    # login_success | login_failed | new_device | password_reset_requested | password_reset | password_changed |
    # email_verified | session_revoked | logout_all | rate_limited | suspicious_request | admin_role_changed |
    # account_suspended | account_banned | account_restored | payment_anomaly | webhook_rejected | trial_abuse
    type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10), default="info")  # info | warning | critical
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    request_id: Mapped[str | None] = mapped_column(String(40), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = created()


class LegalDocument(Base):
    """Every published version is kept; a new version is a new row."""

    __tablename__ = "legal_documents"
    __table_args__ = (UniqueConstraint("document_type", "version"),)
    id: Mapped[uuid.UUID] = pk()
    document_type: Mapped[str] = mapped_column(String(30))  # terms | privacy | cookie | refund | acceptable_use | dmca
    version: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    summary_of_changes: Mapped[str | None] = mapped_column(Text)
    requires_acceptance: Mapped[bool] = mapped_column(Boolean, default=False)  # users must accept to continue
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | published | archived
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = user_fk(nullable=True, ondelete="SET NULL", index=False)
    created_at: Mapped[datetime] = created()


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),
                      UniqueConstraint("user_id", "dedupe_key"))
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk(index=False)
    type: Mapped[str] = mapped_column(String(20))  # system | security | billing | usage | product | account
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str | None] = mapped_column(String(300))
    dedupe_key: Mapped[str | None] = mapped_column(String(120))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created()


class EmailOutbox(Base):
    """Transactional emails are queued here and sent by the worker with retries, never inside a request."""

    __tablename__ = "email_outbox"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID | None] = user_fk(nullable=True, ondelete="SET NULL")
    to_email: Mapped[str] = mapped_column(String(320))
    template: Mapped[str] = mapped_column(String(40))
    subject: Mapped[str] = mapped_column(String(300))
    body_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)  # queued | sent | failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    send_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created()


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    __table_args__ = (Index("ix_analytics_name_created", "name", "created_at"),
                      Index("ix_analytics_user_created", "user_id", "created_at"))
    id: Mapped[uuid.UUID] = pk()
    name: Mapped[str] = mapped_column(String(60))
    user_id: Mapped[uuid.UUID | None] = user_fk(nullable=True, ondelete="SET NULL", index=False)
    anonymous_id: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(40))
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApiRequest(Base):
    """One row per API request (metadata only, never bodies). Kept for API_LOG_RETENTION_DAYS."""

    __tablename__ = "api_requests"
    __table_args__ = (Index("ix_api_requests_created", "created_at"), Index("ix_api_requests_user_created", "user_id", "created_at"),
                      Index("ix_api_requests_route_created", "route", "created_at"))
    id: Mapped[uuid.UUID] = pk()
    request_id: Mapped[str] = mapped_column(String(40), unique=True)
    user_id: Mapped[uuid.UUID | None] = user_fk(nullable=True, ondelete="SET NULL", index=False)
    method: Mapped[str] = mapped_column(String(8))
    route: Mapped[str] = mapped_column(String(200))  # route template, e.g. /api/v1/lessons/{lesson_id}
    status: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(60))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("user_id", "key"),)
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk(index=False)
    key: Mapped[str] = mapped_column(String(100))
    route: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="processing")  # processing | done
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[Any | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created()


class SupportTicket(TimestampMixin, Base):
    __tablename__ = "support_tickets"
    id: Mapped[uuid.UUID] = pk()
    number: Mapped[int] = mapped_column(Integer, unique=True)
    user_id: Mapped[uuid.UUID] = user_fk()
    kind: Mapped[str] = mapped_column(String(20))  # support | bug | billing | feature_request
    subject: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)  # open | pending | resolved | closed | planned | declined
    priority: Mapped[str] = mapped_column(String(10), default="normal")  # low | normal | high | urgent
    category: Mapped[str | None] = mapped_column(String(60))
    assigned_to: Mapped[uuid.UUID | None] = user_fk(nullable=True, ondelete="SET NULL", index=False)
    request_id: Mapped[str | None] = mapped_column(String(40))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TicketMessage(Base):
    __tablename__ = "ticket_messages"
    id: Mapped[uuid.UUID] = pk()
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("support_tickets.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[uuid.UUID | None] = user_fk(nullable=True, ondelete="SET NULL", index=False)
    body: Mapped[str] = mapped_column(Text)
    internal: Mapped[bool] = mapped_column(Boolean, default=False)  # staff-only note
    created_at: Mapped[datetime] = created()


class Announcement(Base):
    __tablename__ = "announcements"
    id: Mapped[uuid.UUID] = pk()
    kind: Mapped[str] = mapped_column(String(20), default="product")  # maintenance | product | feature | important
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str | None] = mapped_column(String(300))
    audience: Mapped[str] = mapped_column(String(20), default="teachers")  # teachers | everyone
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = user_fk(nullable=True, ondelete="SET NULL", index=False)
    created_at: Mapped[datetime] = created()


class UserNote(Base):
    """Internal staff notes about an account. Never shown to the user."""

    __tablename__ = "user_notes"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    author_id: Mapped[uuid.UUID | None] = user_fk(nullable=True, ondelete="SET NULL", index=False)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created()


class TrialGrant(Base):
    """One free trial per normalised email, kept even if the account is deleted (hash only)."""

    __tablename__ = "trial_grants"
    id: Mapped[uuid.UUID] = pk()
    email_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[uuid.UUID | None] = user_fk(nullable=True, ondelete="SET NULL", index=False)
    created_at: Mapped[datetime] = created()


class ProviderHealth(Base):
    """Circuit-breaker state shared by API and worker processes."""

    __tablename__ = "provider_health"
    provider: Mapped[str] = mapped_column(String(30), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    successes: Mapped[int] = mapped_column(Integer, default=0)
    open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    avg_latency_ms: Mapped[float | None] = mapped_column(Float)
