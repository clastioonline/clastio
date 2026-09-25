"""Subscriptions and payments.

`PaymentProvider` keeps the app independent of one gateway. Stripe is implemented (it operates in the UAE and
has complete subscription tooling); Razorpay (India) and manual invoicing (schools) plug in the same way.
Webhooks are signature-verified and idempotent (webhook_events has a unique (provider, event_id)).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.errors import AppError
from app.core.logging import log
from app.models import Payment, Plan, Subscription, User, WebhookEvent
from app.services.usage import DEFAULT_PLANS, active_subscription

logger = logging.getLogger("billing")


def _ts(v: Any) -> datetime | None:
    return datetime.fromtimestamp(int(v), UTC) if v else None


async def seed_plans(db: AsyncSession) -> None:
    for p in DEFAULT_PLANS:
        row = await db.get(Plan, p["code"])
        if row is None:
            db.add(Plan(**p))
    await db.flush()


class StripeProvider:
    name = "stripe"

    def __init__(self) -> None:
        import stripe

        s = get_settings()
        if not s.stripe_secret_key:
            raise AppError("billing_not_configured", "Online payments are not configured yet.", 503)
        self.stripe = stripe
        self.client = stripe.StripeClient(s.stripe_secret_key)
        self.settings = s

    def _line_item(self, plan: Plan, interval: str) -> dict[str, Any]:
        price_id = self.settings.stripe_prices.get(f"{plan.code}_{interval}ly") or \
            self.settings.stripe_prices.get(f"{plan.code}_{interval}")
        if price_id:
            return {"price": price_id, "quantity": 1}
        amount = plan.price_annual_aed if interval == "year" else plan.price_monthly_aed
        return {"price_data": {"currency": "aed", "unit_amount": int(float(amount) * 100),
                               "recurring": {"interval": interval},
                               "product_data": {"name": f"AI Teacher Assistant — {plan.name}"}}, "quantity": 1}

    async def checkout(self, user: User, plan: Plan, interval: str, customer_id: str | None) -> str:
        web = self.settings.public_web_url
        params: dict[str, Any] = {
            "mode": "subscription", "line_items": [self._line_item(plan, interval)],
            "success_url": f"{web}/billing?status=success&session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{web}/billing?status=cancelled",
            "client_reference_id": str(user.id),
            "metadata": {"user_id": str(user.id), "plan_code": plan.code, "interval": interval},
            "subscription_data": {"metadata": {"user_id": str(user.id), "plan_code": plan.code}},
            "allow_promotion_codes": True,
            "billing_address_collection": "required",
        }
        if customer_id:
            params["customer"] = customer_id
        else:
            params["customer_email"] = user.email
        session = await self.client.v1.checkout.sessions.create_async(params=params)
        return session.url

    async def portal(self, customer_id: str) -> str:
        session = await self.client.v1.billing_portal.sessions.create_async(
            params={"customer": customer_id, "return_url": f"{self.settings.public_web_url}/billing"})
        return session.url

    async def cancel(self, subscription_id: str) -> None:
        await self.client.v1.subscriptions.update_async(subscription_id, params={"cancel_at_period_end": True})

    def verify(self, payload: bytes, signature: str | None) -> dict[str, Any]:
        secret = self.settings.stripe_webhook_secret
        if not secret:
            raise AppError("billing_not_configured", "Webhook secret not configured", 503)
        try:
            self.stripe.WebhookSignature.verify_header(payload.decode(), signature or "", secret, tolerance=300)
        except Exception as e:  # stripe.SignatureVerificationError
            raise AppError("invalid_signature", "Invalid webhook signature", 400) from e
        import json

        return json.loads(payload)


def get_provider(name: str = "stripe") -> StripeProvider:
    if name == "stripe":
        return StripeProvider()
    raise AppError("billing_provider_unknown", f"Unknown provider {name}", 400)


async def start_checkout(db: AsyncSession, user: User, plan_code: str, interval: str) -> str:
    plan = await db.get(Plan, plan_code)
    if plan is None or not plan.active or plan.code == "free":
        raise AppError("bad_request", "Unknown plan", 400)
    if interval not in ("month", "year"):
        raise AppError("bad_request", "Interval must be month or year", 400)
    sub = await active_subscription(db, user.id)
    return await get_provider().checkout(user, plan, interval, sub.provider_customer_id if sub else None)


async def open_portal(db: AsyncSession, user: User) -> str:
    sub = await active_subscription(db, user.id)
    if not sub or sub.provider != "stripe" or not sub.provider_customer_id:
        raise AppError("no_subscription", "You don't have an online subscription to manage.", 404)
    return await get_provider().portal(sub.provider_customer_id)


async def cancel_subscription(db: AsyncSession, user: User) -> Subscription:
    sub = await active_subscription(db, user.id)
    if not sub:
        raise AppError("no_subscription", "No active subscription.", 404)
    if sub.provider == "stripe" and sub.provider_subscription_id:
        await get_provider().cancel(sub.provider_subscription_id)
    sub.cancel_at_period_end = True
    await db.commit()
    return sub


async def set_manual_plan(db: AsyncSession, user_id: uuid.UUID, plan_code: str, *, months: int = 1) -> Subscription:
    """Admin / school invoicing: grant a plan without an online payment."""
    from dateutil.relativedelta import relativedelta  # type: ignore[import-untyped]

    for s in (await db.execute(select(Subscription).where(Subscription.user_id == user_id,
                                                          Subscription.status.in_(("active", "trialing")))
                               )).scalars().all():
        s.status = "canceled"
    now = utcnow()
    sub = Subscription(user_id=user_id, plan_code=plan_code, status="active", provider="manual",
                       interval="year" if months >= 12 else "month", current_period_start=now,
                       current_period_end=now + relativedelta(months=months))
    db.add(sub)
    await db.commit()
    return sub


# --------------------------------------------------------------------------- webhooks


async def _find_sub(db: AsyncSession, provider_sub_id: str | None) -> Subscription | None:
    if not provider_sub_id:
        return None
    return (await db.execute(select(Subscription).where(Subscription.provider_subscription_id == provider_sub_id))
            ).scalars().first()


async def handle_stripe_event(db: AsyncSession, event: dict[str, Any]) -> str:
    try:
        db.add(WebhookEvent(provider="stripe", event_id=event["id"], type=event["type"], payload=event))
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return "duplicate"
    obj = event["data"]["object"]
    etype = event["type"]
    if etype == "checkout.session.completed" and obj.get("mode") == "subscription":
        meta = obj.get("metadata") or {}
        user_id = uuid.UUID(meta.get("user_id") or obj.get("client_reference_id"))
        sub = await _find_sub(db, obj.get("subscription"))
        for old in (await db.execute(select(Subscription).where(Subscription.user_id == user_id,
                                                                Subscription.status.in_(("active", "trialing"))))
                    ).scalars().all():
            if not sub or old.id != sub.id:
                old.status = "canceled"
        if sub is None:
            sub = Subscription(user_id=user_id, provider="stripe", provider_subscription_id=obj.get("subscription"))
            db.add(sub)
        sub.plan_code = meta.get("plan_code", "teacher")
        sub.interval = meta.get("interval", "month")
        sub.provider_customer_id = obj.get("customer")
        sub.status = "active"
        sub.current_period_start = sub.current_period_start or utcnow()
    elif etype in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
        sub = await _find_sub(db, obj.get("id"))
        meta = obj.get("metadata") or {}
        if sub is None and meta.get("user_id"):
            sub = Subscription(user_id=uuid.UUID(meta["user_id"]), provider="stripe", provider_subscription_id=obj["id"],
                               plan_code=meta.get("plan_code", "teacher"))
            db.add(sub)
        if sub is not None:
            status = obj.get("status", "active")
            sub.status = {"incomplete_expired": "canceled", "unpaid": "past_due", "incomplete": "past_due"}.get(
                status, status)
            if etype == "customer.subscription.deleted":
                sub.status = "canceled"
            item = ((obj.get("items") or {}).get("data") or [{}])[0]
            sub.current_period_start = _ts(obj.get("current_period_start") or item.get("current_period_start")) \
                or sub.current_period_start
            sub.current_period_end = _ts(obj.get("current_period_end") or item.get("current_period_end")) \
                or sub.current_period_end
            sub.cancel_at_period_end = bool(obj.get("cancel_at_period_end"))
            sub.provider_customer_id = obj.get("customer") or sub.provider_customer_id
            interval = ((item.get("price") or {}).get("recurring") or {}).get("interval")
            if interval:
                sub.interval = interval
            if meta.get("plan_code"):
                sub.plan_code = meta["plan_code"]
    elif etype in ("invoice.paid", "invoice.payment_succeeded"):
        sub_id = obj.get("subscription") or ((obj.get("parent") or {}).get("subscription_details") or {}).get(
            "subscription")
        sub = await _find_sub(db, sub_id)
        user_id = sub.user_id if sub else None
        if user_id and not (await db.execute(select(Payment).where(Payment.provider_ref == obj["id"]))).first():
            tax = sum((t.get("amount") or 0) for t in (obj.get("total_taxes") or obj.get("total_tax_amounts") or []))
            db.add(Payment(user_id=user_id, provider="stripe", provider_ref=obj["id"],
                           amount=(obj.get("amount_paid") or 0) / 100, currency=(obj.get("currency") or "aed").upper(),
                           tax_amount=tax / 100, status="paid", invoice_url=obj.get("hosted_invoice_url")))
        if sub and sub.status == "past_due":
            sub.status = "active"
    elif etype == "invoice.payment_failed":
        sub = await _find_sub(db, obj.get("subscription"))
        if sub:
            sub.status = "past_due"
    ev = (await db.execute(select(WebhookEvent).where(WebhookEvent.provider == "stripe",
                                                      WebhookEvent.event_id == event["id"]))).scalars().first()
    ev.processed_at = utcnow()
    await db.commit()
    log(logger, logging.INFO, "stripe_event", type=etype)
    return "processed"
