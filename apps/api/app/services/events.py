"""Security events, admin audit records and product analytics: the three append-only logs."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import log, request_id_var
from app.core.request_meta import client_ip, user_agent
from app.models import AnalyticsEvent, AuditLog, SecurityEvent

logger = logging.getLogger("events")

WARNING_EVENTS = {"login_failed", "rate_limited", "new_device", "session_revoked", "webhook_rejected", "trial_abuse"}
CRITICAL_EVENTS = {"account_banned", "admin_role_changed", "payment_anomaly", "suspicious_request"}


def security_event(db: AsyncSession, type_: str, *, user_id: uuid.UUID | None = None, request: Request | None = None,
                   severity: str | None = None, **details: Any) -> SecurityEvent:
    sev = severity or ("critical" if type_ in CRITICAL_EVENTS else "warning" if type_ in WARNING_EVENTS else "info")
    ev = SecurityEvent(type=type_, severity=sev, user_id=user_id, ip=client_ip(request), user_agent=user_agent(request),
                       request_id=request_id_var.get(), details=details)
    db.add(ev)
    log(logger, logging.WARNING if sev != "info" else logging.INFO, "security_event", type=type_, severity=sev,
        user_id=str(user_id) if user_id else None)
    if sev == "critical" or type_ == "provider_circuit_open":
        import asyncio

        from app.services.notifications import alert_staff_detached

        alert = "provider_down" if type_ == "provider_circuit_open" else "security_critical"
        summary = ", ".join(f"{k}={v}" for k, v in details.items() if k not in ("error",))[:300]
        try:  # after the caller's transaction, in its own session
            asyncio.get_running_loop().create_task(alert_staff_detached(
                alert, dedupe_key=f"{type_}:{request_id_var.get() or ev.id}", type=type_, summary=summary,
                provider=details.get("provider", ""), error=str(details.get("error", ""))[:300]))
        except RuntimeError:
            pass
    return ev


def audit(db: AsyncSession, actor_id: uuid.UUID | None, action: str, *, request: Request | None = None,
          target_user: uuid.UUID | str | None = None, target_type: str | None = None, target_id: str | None = None,
          before: dict | None = None, after: dict | None = None, reason: str | None = None,
          **details: Any) -> AuditLog:
    """Record a sensitive action. `target` is the affected user, so an account's history is one query."""
    row = AuditLog(actor_id=actor_id, action=action, target=str(target_user) if target_user else None,
                   target_type=target_type, target_id=target_id, before=before, after=after, reason=reason,
                   details=details, ip=client_ip(request), user_agent=user_agent(request),
                   request_id=request_id_var.get())
    db.add(row)
    return row


def track(db: AsyncSession, name: str, *, user_id: uuid.UUID | None = None, anonymous_id: str | None = None,
          **properties: Any) -> None:
    """Product analytics. Properties are identifiers and counts, never content or personal data."""
    db.add(AnalyticsEvent(name=name, user_id=user_id, anonymous_id=anonymous_id, request_id=request_id_var.get(),
                          properties=properties))
