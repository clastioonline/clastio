"""Subscriptions and payments.

Two gateways share one interface (checkout, one-time checkout, portal, cancel, webhook verification):
- Dodo Payments: a merchant of record, so it collects and remits VAT/GST and supports cards, UPI and local
  methods in the UAE and India. Uses the official `dodopayments` SDK and Standard Webhooks signatures.
- Stripe: direct gateway with complete subscription tooling.
Admins choose the active gateway in the `billing` setting ("auto" prefers Dodo when its key is set). Manual
plans (schools, invoices) need neither. Webhooks are signature-verified and idempotent (webhook_events has a
unique (provider, event_id)).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.errors import AppError
from app.core.logging import log
from app.models import Payment, Plan, Subscription, User, WebhookEvent
from app.services.settings import get_setting
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
                               "product_data": {"name": f"PPT Genie — {plan.name}"}}, "quantity": 1}

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

    async def checkout_one_time(self, user: User, *, name: str, amount_aed: float, product_id: str | None,
                                metadata: dict[str, str]) -> str:
        web = self.settings.public_web_url
        session = await self.client.v1.checkout.sessions.create_async(params={
            "mode": "payment",
            "line_items": [{"price_data": {"currency": "aed", "unit_amount": int(float(amount_aed) * 100),
                                           "product_data": {"name": name}}, "quantity": 1}],
            "success_url": f"{web}/media?status=success", "cancel_url": f"{web}/media?status=cancelled",
            "client_reference_id": str(user.id), "customer_email": user.email,
            "metadata": {"user_id": str(user.id), **metadata},
            "payment_intent_data": {"metadata": {"user_id": str(user.id), **metadata}},
        })
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


class DodoProvider:
    """Dodo Payments through the official SDK. Products (subscriptions and one-time packs) are created in the Dodo
    dashboard; their ids are mapped to plans and packs in Admin -> Payments."""

    name = "dodo"

    def __init__(self, products: dict[str, str] | None = None) -> None:
        s = get_settings()
        if not s.dodo_payments_api_key:
            raise AppError("billing_not_configured", "Online payments are not configured yet.", 503)
        from dodopayments import AsyncDodoPayments

        self.settings = s
        self.client = AsyncDodoPayments(bearer_token=s.dodo_payments_api_key,
                                        environment=s.dodo_payments_environment)
        self.products = {**s.dodo_products, **(products or {})}

    def _customer(self, user: User, customer_id: str | None) -> dict[str, Any]:
        if customer_id:
            return {"customer_id": customer_id}
        return {"email": user.email, "name": user.name or user.email.split("@")[0]}

    async def checkout(self, user: User, plan: Plan, interval: str, customer_id: str | None) -> str:
        product_id = self.products.get(f"{plan.code}_{interval}")
        if not product_id:
            raise AppError("billing_not_configured",
                           f"The {plan.name} {interval}ly plan isn't available for online payment yet.", 503)
        session = await self.client.checkout_sessions.create(
            product_cart=[{"product_id": product_id, "quantity": 1}],
            customer=self._customer(user, customer_id),
            return_url=f"{self.settings.public_web_url}/billing?status=success",
            metadata={"user_id": str(user.id), "plan_code": plan.code, "interval": interval,
                      "kind": "subscription"})
        return session.checkout_url

    async def checkout_one_time(self, user: User, *, name: str, amount_aed: float, product_id: str | None,
                                metadata: dict[str, str]) -> str:
        if not product_id:
            raise AppError("billing_not_configured", f"{name} isn't available for online payment yet.", 503)
        session = await self.client.checkout_sessions.create(
            product_cart=[{"product_id": product_id, "quantity": 1}],
            customer=self._customer(user, None),
            return_url=f"{self.settings.public_web_url}/media?status=success",
            metadata={"user_id": str(user.id), **metadata})
        return session.checkout_url

    async def portal(self, customer_id: str) -> str:
        session = await self.client.customers.customer_portal.create(
            customer_id, return_url=f"{self.settings.public_web_url}/billing")
        return session.link

    async def cancel(self, subscription_id: str) -> None:
        await self.client.subscriptions.update(subscription_id, cancel_at_next_billing_date=True)

    def verify(self, payload: bytes, headers: dict[str, str]) -> dict[str, Any]:
        return verify_dodo_webhook(payload, headers)


def verify_dodo_webhook(payload: bytes, headers: dict[str, str]) -> dict[str, Any]:
    """Standard Webhooks signature check (webhook-id, webhook-timestamp, webhook-signature headers).
    Needs only the webhook secret, not the API key."""
    key = get_settings().dodo_payments_webhook_key
    if not key:
        raise AppError("billing_not_configured", "Webhook secret not configured", 503)
    from standardwebhooks import Webhook

    try:
        Webhook(key).verify(payload.decode(), headers)
    except Exception as e:  # standardwebhooks.WebhookVerificationError
        raise AppError("invalid_signature", "Invalid webhook signature", 400) from e
    import json

    return json.loads(payload)


PaymentProvider = StripeProvider | DodoProvider


async def active_provider_name() -> str | None:
    """The gateway checkout should use, or None when no online payments are configured."""
    s = get_settings()
    choice = (await get_setting("billing")).get("provider", "auto")
    available = {"dodo": bool(s.dodo_payments_api_key), "stripe": bool(s.stripe_secret_key)}
    if choice in available:
        return choice if available[choice] else None
    return next((name for name in ("dodo", "stripe") if available[name]), None)


async def get_provider(name: str | None = None) -> PaymentProvider:
    name = name or await active_provider_name()
    if name == "dodo":
        return DodoProvider((await get_setting("billing")).get("dodo_products") or {})
    if name == "stripe":
        return StripeProvider()
    if name is None:
        raise AppError("billing_not_configured", "Online payments are not configured yet.", 503)
    raise AppError("billing_provider_unknown", f"Unknown provider {name}", 400)


async def start_checkout(db: AsyncSession, user: User, plan_code: str, interval: str) -> str:
    plan = await db.get(Plan, plan_code)
    if plan is None or not plan.active or plan.code == "free":
        raise AppError("bad_request", "Unknown plan", 400)
    if interval not in ("month", "year"):
        raise AppError("bad_request", "Interval must be month or year", 400)
    sub = await active_subscription(db, user.id)
    provider = await get_provider()
    customer_id = sub.provider_customer_id if sub and sub.provider == provider.name else None
    return await provider.checkout(user, plan, interval, customer_id)


async def open_portal(db: AsyncSession, user: User) -> str:
    sub = await active_subscription(db, user.id)
    if not sub or sub.provider not in ("stripe", "dodo") or not sub.provider_customer_id:
        raise AppError("no_subscription", "You don't have an online subscription to manage.", 404)
    return await (await get_provider(sub.provider)).portal(sub.provider_customer_id)


async def cancel_subscription(db: AsyncSession, user: User) -> Subscription:
    sub = await active_subscription(db, user.id)
    if not sub:
        raise AppError("no_subscription", "No active subscription.", 404)
    if sub.provider in ("stripe", "dodo") and sub.provider_subscription_id:
        await (await get_provider(sub.provider)).cancel(sub.provider_subscription_id)
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
    """Apply one verified Stripe event. Bookkeeping (idempotency, status, retries) is done by process_webhook."""
    obj = event["data"]["object"]
    etype = event["type"]
    changes = _SubChanges()
    result = "processed"
    if etype == "checkout.session.completed" and obj.get("mode") == "payment" and obj.get("payment_status") == "paid":
        meta = obj.get("metadata") or {}
        if meta.get("kind") == "media_pack" and meta.get("user_id"):
            user_id = uuid.UUID(meta["user_id"])
            await grant_media_pack(db, user_id, meta.get("pack_code", ""), f"stripe:{obj['id']}")
            if not (await db.execute(select(Payment).where(Payment.provider_ref == obj["id"]))).first():
                db.add(Payment(user_id=user_id, provider="stripe", provider_ref=obj["id"],
                               amount=(obj.get("amount_total") or 0) / 100,
                               currency=(obj.get("currency") or "aed").upper(),
                               tax_amount=((obj.get("total_details") or {}).get("amount_tax") or 0) / 100,
                               status="paid", invoice_url=None))
    elif etype == "checkout.session.completed" and obj.get("mode") == "subscription":
        meta = obj.get("metadata") or {}
        user_id = uuid.UUID(meta.get("user_id") or obj.get("client_reference_id"))
        sub = await _find_sub(db, obj.get("subscription"))
        for old in (await db.execute(select(Subscription).where(Subscription.user_id == user_id,
                                                                Subscription.status.in_(("active", "trialing"))))
                    ).scalars().all():
            if not sub or old.id != sub.id:
                changes.see(old)
                old.status = "canceled"
        if sub is None:
            sub = Subscription(user_id=user_id, provider="stripe", provider_subscription_id=obj.get("subscription"))
            db.add(sub)
        changes.see(sub)
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
            changes.see(sub)
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
            await _receipt(db, user_id, obj["id"], (obj.get("amount_paid") or 0) / 100,
                           (obj.get("currency") or "aed").upper())
        if sub and sub.status == "past_due":
            changes.see(sub)
            sub.status = "active"
    elif etype == "invoice.payment_failed":
        sub = await _find_sub(db, obj.get("subscription"))
        if sub:
            changes.see(sub)
            sub.status = "past_due"
            err = (obj.get("last_finalization_error") or {}).get("message") or obj.get("billing_reason")
            await _record_failed_payment(db, sub.user_id, "stripe", obj["id"], (obj.get("amount_due") or 0) / 100,
                                         (obj.get("currency") or "aed").upper(), err, sub.provider_subscription_id)
    else:
        result = "ignored"
    await changes.apply(db)
    log(logger, logging.INFO, "stripe_event", type=etype)
    return result


# --------------------------------------------------------------------------- media packs (shared by gateways)


async def grant_media_pack(db: AsyncSession, user_id: uuid.UUID, pack_code: str, ref: str) -> int:
    """Add a purchased pack's media credits once per payment reference. Returns credits added (0 if repeated)."""
    from app.models import CreditLedger

    if (await db.execute(select(CreditLedger).where(CreditLedger.ref == ref,
                                                    CreditLedger.resource == "media_credits"))).first():
        return 0
    packs = {p["code"]: p for p in (await get_setting("media")).get("packs", [])}
    pack = packs.get(pack_code)
    if pack is None:
        log(logger, logging.ERROR, "media_pack_unknown", pack=pack_code, ref=ref)
        return 0
    from app.services.usage import ledger_entry

    db.add(ledger_entry(user_id, int(pack["credits"]), f"media_pack:{pack_code}", ref=ref, resource="media_credits",
                        event_type="CREDIT_PURCHASE"))
    return int(pack["credits"])


# --------------------------------------------------------------------------- Dodo Payments webhooks

DODO_STATUS = {"active": "active", "on_hold": "past_due", "past_due": "past_due", "paused": "past_due",
               "pending": "past_due", "cancelled": "canceled", "failed": "canceled", "expired": "canceled"}


def _iso(v: Any) -> datetime | None:
    if not v:
        return None
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


async def handle_dodo_event(db: AsyncSession, event: dict[str, Any], event_id: str = "") -> str:
    """Apply one verified Dodo Payments event. Bookkeeping is done by process_webhook."""
    changes = _SubChanges()
    result = "processed"
    etype = event.get("type", "")
    data = event.get("data") or {}
    meta = data.get("metadata") or {}
    customer_id = (data.get("customer") or {}).get("customer_id")
    products = (await get_setting("billing")).get("dodo_products") or {}
    by_product = {v: k for k, v in {**get_settings().dodo_products, **products}.items() if v}

    if etype.startswith("subscription."):
        sub = await _find_sub(db, data.get("subscription_id"))
        plan_code, interval = meta.get("plan_code"), meta.get("interval")
        if not plan_code and data.get("product_id") in by_product:  # e.g. a plan change made in the portal
            plan_code, _, interval = by_product[data["product_id"]].rpartition("_")
        if sub is None and meta.get("user_id"):
            sub = Subscription(user_id=uuid.UUID(meta["user_id"]), provider="dodo",
                               provider_subscription_id=data.get("subscription_id"), plan_code=plan_code or "teacher")
            db.add(sub)
        if sub is not None:
            changes.see(sub)
            status = DODO_STATUS.get(data.get("status") or etype.split(".", 1)[1], sub.status or "active")
            if etype in ("subscription.cancelled", "subscription.expired", "subscription.failed"):
                status = "canceled"
            if status == "active":  # one active plan per teacher
                for old in (await db.execute(select(Subscription).where(
                        Subscription.user_id == sub.user_id, Subscription.status.in_(("active", "trialing")))
                        )).scalars().all():
                    if old.id != sub.id:
                        changes.see(old)
                        old.status = "canceled"
            sub.status = status
            sub.plan_code = plan_code or sub.plan_code
            freq = str(data.get("payment_frequency_interval") or "").lower()
            sub.interval = interval or ("year" if freq == "year" else "month" if freq else sub.interval)
            sub.provider_customer_id = customer_id or sub.provider_customer_id
            sub.current_period_start = _iso(data.get("previous_billing_date")) or sub.current_period_start or utcnow()
            sub.current_period_end = _iso(data.get("next_billing_date")) or sub.current_period_end
            sub.cancel_at_period_end = bool(data.get("cancel_at_next_billing_date"))
    elif etype == "payment.succeeded":
        payment_id = data.get("payment_id")
        sub = await _find_sub(db, data.get("subscription_id"))
        user_id = sub.user_id if sub else (uuid.UUID(meta["user_id"]) if meta.get("user_id") else None)
        if user_id and payment_id:
            pack_code = meta.get("pack_code") if meta.get("kind") == "media_pack" else None
            if not pack_code:  # metadata missing: fall back to the product bought
                pack_ids = {p.get("dodo_product_id"): p["code"] for p in (await get_setting("media")).get("packs", [])
                            if p.get("dodo_product_id")}
                pack_code = next((pack_ids[i.get("product_id")] for i in data.get("product_cart") or []
                                  if i.get("product_id") in pack_ids), None)
            if pack_code:
                await grant_media_pack(db, user_id, pack_code, f"dodo:{payment_id}")
            if not (await db.execute(select(Payment).where(Payment.provider_ref == payment_id))).first():
                db.add(Payment(user_id=user_id, provider="dodo", provider_ref=payment_id,
                               amount=(data.get("total_amount") or 0) / 100,
                               currency=(data.get("currency") or "AED").upper(),
                               tax_amount=(data.get("tax") or 0) / 100, status="paid",
                               invoice_url=data.get("invoice_url")))
                await _receipt(db, user_id, payment_id, (data.get("total_amount") or 0) / 100,
                               (data.get("currency") or "AED").upper())
        if sub and sub.status == "past_due":
            changes.see(sub)
            sub.status = "active"
    elif etype == "payment.failed":
        sub = await _find_sub(db, data.get("subscription_id"))
        user_id = sub.user_id if sub else (uuid.UUID(meta["user_id"]) if meta.get("user_id") else None)
        if sub:
            changes.see(sub)
            sub.status = "past_due"
        if user_id and data.get("payment_id"):
            await _record_failed_payment(db, user_id, "dodo", data["payment_id"], (data.get("total_amount") or 0) / 100,
                                         (data.get("currency") or "AED").upper(),
                                         data.get("error_message") or data.get("error_code"),
                                         sub.provider_subscription_id if sub else None)
    else:
        result = "ignored"
    await changes.apply(db)
    log(logger, logging.INFO, "dodo_event", type=etype)
    return result


# --------------------------------------------------------------------------- webhook bookkeeping & side effects


class _SubChanges:
    """Remembers each subscription's status before a webhook touched it, then reacts to real transitions
    (analytics, in-app notice and email) once the event has been applied."""

    def __init__(self) -> None:
        self.before: dict[int, tuple[Subscription, str | None]] = {}

    def see(self, sub: Subscription) -> None:
        self.before.setdefault(id(sub), (sub, sub.status if sub.id else None))

    async def apply(self, db: AsyncSession) -> None:
        from app.services.events import track
        from app.services.notify import notify, queue_email

        link = f"{get_settings().public_web_url}/billing"
        for sub, before in self.before.values():
            after = sub.status
            if before == after:
                continue
            user = await db.get(User, sub.user_id)
            plan = await db.get(Plan, sub.plan_code)
            plan_name = plan.name if plan else sub.plan_code
            if after == "active" and before in (None, "trialing", "canceled"):
                track(db, "subscription_activated", user_id=sub.user_id, plan=sub.plan_code, provider=sub.provider)
                await notify(db, sub.user_id, "billing", f"You're on {plan_name}", "Thank you for subscribing.",
                             "/billing", dedupe_key=f"sub_active:{sub.provider_subscription_id or sub.id}")
                if user:
                    queue_email(db, user, "subscription_confirmed", link=link, plan=plan_name)
            elif after == "canceled":
                sub.canceled_at = sub.canceled_at or utcnow()
                track(db, "subscription_canceled", user_id=sub.user_id, plan=sub.plan_code, provider=sub.provider)
                if user and sub.provider in ("stripe", "dodo"):
                    queue_email(db, user, "subscription_cancelled", link=link)
            elif after == "past_due":
                track(db, "payment_failed", user_id=sub.user_id, plan=sub.plan_code, provider=sub.provider)
                await notify(db, sub.user_id, "billing", "We couldn't take your payment",
                             "Update your payment method to keep your plan.", "/billing")
                if user:
                    queue_email(db, user, "payment_failed", link=link)


async def _record_failed_payment(db: AsyncSession, user_id: uuid.UUID, provider: str, ref: str, amount: float,
                                 currency: str, reason: str | None, subscription_ref: str | None) -> None:
    if (await db.execute(select(Payment.id).where(Payment.provider_ref == ref))).first():
        return
    db.add(Payment(user_id=user_id, provider=provider, provider_ref=ref, amount=amount, currency=currency,
                   status="failed", failure_reason=(reason or "")[:500] or None, subscription_ref=subscription_ref))
    from app.services.notifications import alert_staff

    user = await db.get(User, user_id)
    await alert_staff(db, "payment_failed", dedupe_key=f"payfail:{ref}", email=user.email if user else "?",
                      amount=f"{currency} {amount:,.2f}", reason=f"— {reason}" if reason else "")


async def _receipt(db: AsyncSession, user_id: uuid.UUID, ref: str, amount: float, currency: str) -> None:
    from app.services.notifications import send

    user = await db.get(User, user_id)
    if user:
        await send(db, user, "payment_receipt", dedupe_key=f"receipt:{ref}", amount=f"{currency} {amount:,.2f}")


async def process_webhook(db: AsyncSession, *, provider: str, event_id: str, event_type: str,
                          event: dict[str, Any], raw: bytes, handler, request=None) -> str:
    """Idempotent webhook processing with a durable record of every delivery.

    1. The event row is inserted in its own transaction (unique provider + event_id), so it survives a failure.
    2. A delivery already processed returns "duplicate" and changes nothing (no double credits or charges).
    3. The same event id with a different payload is rejected and raised as a security event.
    4. A failure is stored with its error and retry count; the 500 makes the gateway retry later.
    """
    import hashlib

    from sqlalchemy.dialects.postgresql import insert

    from app.core.db import get_sessionmaker, uuid7
    from app.services.events import security_event

    digest = hashlib.sha256(raw).hexdigest()
    async with get_sessionmaker()() as s:
        res = await s.execute(insert(WebhookEvent).values(
            id=uuid7(), provider=provider, event_id=event_id, type=event_type[:100], payload=event,
            payload_hash=digest, status="received", retry_count=0, created_at=utcnow())
            .on_conflict_do_nothing(index_elements=["provider", "event_id"]))
        if not res.rowcount:
            ev = (await s.execute(select(WebhookEvent).where(WebhookEvent.provider == provider,
                                                             WebhookEvent.event_id == event_id)
                                  .with_for_update())).scalars().one()
            if ev.payload_hash and ev.payload_hash != digest:
                security_event(s, "webhook_rejected", request=request, severity="critical", provider=provider,
                               event_id=event_id, reason="payload_changed")
                await s.commit()
                return "rejected"
            if ev.status in ("processed", "ignored"):
                await s.commit()
                return "duplicate"
            ev.retry_count += 1
        await s.commit()
    try:
        result = await handler(db, event)
        await db.flush()
    except Exception as e:
        await db.rollback()
        async with get_sessionmaker()() as s:
            ev = (await s.execute(select(WebhookEvent).where(WebhookEvent.provider == provider,
                                                             WebhookEvent.event_id == event_id))).scalars().one()
            ev.status, ev.error_message = "failed", f"{type(e).__name__}: {str(e)[:900]}"
            await s.commit()
        log(logger, logging.ERROR, "webhook_failed", provider=provider, type=event_type, error=str(e)[:300])
        from app.services.notifications import alert_staff_detached

        await alert_staff_detached("webhook_failed", dedupe_key=f"whfail:{provider}:{event_id}", provider=provider,
                                   error=f"{event_type}: {type(e).__name__}")
        raise
    ev = (await db.execute(select(WebhookEvent).where(WebhookEvent.provider == provider,
                                                      WebhookEvent.event_id == event_id))).scalars().one()
    ev.status = "ignored" if result == "ignored" else "processed"
    ev.result, ev.error_message, ev.processed_at = result, None, utcnow()
    await db.commit()
    return result
