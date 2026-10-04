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
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.errors import AppError
from app.core.logging import log
from app.models import Payment, Plan, Subscription, SubscriptionCheckout, User, WebhookEvent
from app.services.settings import get_setting
from app.services.usage import DEFAULT_PLANS, active_subscription

logger = logging.getLogger("billing")
PENDING_CHECKOUT_STATUSES = ("creating", "open", "processing")


@dataclass(frozen=True)
class CreatedCheckout:
    id: str
    url: str
    expires_at: datetime


def _ts(v: Any) -> datetime | None:
    return datetime.fromtimestamp(int(v), UTC) if v else None


async def seed_plans(db: AsyncSession) -> None:
    for p in DEFAULT_PLANS:
        row = await db.get(Plan, p["code"])
        if row is None:
            db.add(Plan(**p))
    await db.flush()


async def update_launch_prices(db: AsyncSession) -> list[str]:
    """Explicit catalogue update; never change subscriptions, entitlements or provider prices."""
    changed = []
    for defaults in DEFAULT_PLANS:
        if defaults["code"] == "free":
            continue
        row = await db.get(Plan, defaults["code"])
        if row is None:
            continue
        if (row.price_monthly_aed, row.price_annual_aed) != (defaults["price_monthly_aed"], defaults["price_annual_aed"]):
            row.price_monthly_aed = defaults["price_monthly_aed"]
            row.price_annual_aed = defaults["price_annual_aed"]
            changed.append(row.code)
    await db.flush()
    return changed


def _plan_amount_minor(plan: Plan, interval: str) -> int:
    amount = plan.price_annual_aed if interval == "year" else plan.price_monthly_aed
    return int(Decimal(str(amount)) * 100)


def _check_catalogue_price(plan: Plan, interval: str, *, amount: int | None, currency: str,
                           frequency: str, count: int, active: bool = True) -> None:
    period_matches = (frequency == interval and count == 1) or (interval == "year" and frequency == "month" and count == 12)
    if not active or amount != _plan_amount_minor(plan, interval) or currency.lower() != "aed" or not period_matches:
        raise AppError("billing_price_mismatch", "This plan's payment price is being updated. Please try again later.", 503)


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
        return {"price_data": {"currency": "aed", "unit_amount": _plan_amount_minor(plan, interval),
                               "recurring": {"interval": interval},
                               "product_data": {"name": f"Clastio — {plan.name}"}}, "quantity": 1}

    async def checkout(self, user: User, plan: Plan, interval: str, customer_id: str | None, coupon_code: str | None = None,
                       *, reservation: SubscriptionCheckout | None = None) -> str | CreatedCheckout:
        web = self.settings.public_web_url
        line_item = self._line_item(plan, interval)
        if "price" in line_item:
            try:
                price = await self.client.v1.prices.retrieve_async(line_item["price"])
            except Exception:
                # No checkout has been submitted, so a fresh reservation can
                # be released safely even if this read request times out.
                raise AppError("billing_preparation_unavailable", "We could not verify this plan's payment price. Please try again later.", 503) from None
            recurring = price.recurring
            _check_catalogue_price(plan, interval, amount=price.unit_amount, currency=price.currency,
                                   frequency=recurring.interval if recurring else "", count=recurring.interval_count if recurring else 0,
                                   active=price.active)
        params: dict[str, Any] = {
            "mode": "subscription", "line_items": [line_item],
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
        if coupon_code:
            try:
                promos = await self.client.v1.promotion_codes.list_async(params={"code": coupon_code, "active": True, "limit": 1})
            except Exception:
                raise AppError("billing_preparation_unavailable", "We could not verify this coupon. Please try again later.", 503) from None
            if not promos.data:
                raise AppError("invalid_coupon", "This coupon code is invalid or expired.", 422)
            params.pop("allow_promotion_codes", None)
            params["discounts"] = [{"promotion_code": promos.data[0].id}]
        if reservation:
            params["metadata"]["clastio_checkout_id"] = str(reservation.id)
            params["subscription_data"]["metadata"]["clastio_checkout_id"] = str(reservation.id)
            params["expires_at"] = int(reservation.expires_at.timestamp())
            session = await self.client.v1.checkout.sessions.create_async(params=params,
                options={"idempotency_key": f"subscription-checkout:{reservation.id}"})
            return CreatedCheckout(session.id, session.url, _ts(session.expires_at))
        session = await self.client.v1.checkout.sessions.create_async(params=params)
        return session.url

    async def checkout_state(self, row: SubscriptionCheckout) -> str:
        session = await self.client.v1.checkout.sessions.retrieve_async(row.provider_session_id)
        return {"expired": "expired", "complete": "processing"}.get(session.status, "open")

    async def expire_checkout(self, row: SubscriptionCheckout) -> None:
        await self.client.v1.checkout.sessions.expire_async(row.provider_session_id)

    async def checkout_one_time(self, user: User, *, name: str, amount_aed: float, product_id: str | None,
                                metadata: dict[str, str]) -> str:
        web = self.settings.public_web_url
        session = await self.client.v1.checkout.sessions.create_async(params={
            "mode": "payment",
            "line_items": [{"price_data": {"currency": "aed", "unit_amount": int(Decimal(str(amount_aed)) * 100),
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

    async def checkout(self, user: User, plan: Plan, interval: str, customer_id: str | None, coupon_code: str | None = None,
                       *, reservation: SubscriptionCheckout | None = None) -> str | CreatedCheckout:
        product_id = self.products.get(f"{plan.code}_{interval}")
        if not product_id:
            raise AppError("billing_not_configured",
                           f"The {plan.name} {interval}ly plan isn't available for online payment yet.", 503)
        try:
            product = await self.client.products.retrieve(product_id)
        except Exception:
            raise AppError("billing_preparation_unavailable", "We could not verify this plan's payment price. Please try again later.", 503) from None
        price = product.price
        _check_catalogue_price(plan, interval, amount=getattr(price, "price", None), currency=price.currency,
                               frequency=getattr(price, "payment_frequency_interval", ""),
                               count=getattr(price, "payment_frequency_count", 0),
                               active=price.type == "recurring_price")
        metadata = {"user_id": str(user.id), "plan_code": plan.code, "interval": interval, "kind": "subscription"}
        if reservation:
            metadata["clastio_checkout_id"] = str(reservation.id)
        session = await self.client.checkout_sessions.create(
            product_cart=[{"product_id": product_id, "quantity": 1}],
            customer=self._customer(user, customer_id),
            return_url=f"{self.settings.public_web_url}/billing?status=success",
            metadata=metadata,
            feature_flags={"allow_discount_code": True},
            **({"discount_codes": [coupon_code]} if coupon_code else {}))
        if reservation:
            # Unconfirmed Dodo sessions expire after 24 hours. Starting from
            # response time is conservative; never shorten provider validity.
            return CreatedCheckout(session.session_id, session.checkout_url, utcnow() + timedelta(hours=24))
        return session.checkout_url

    async def checkout_state(self, row: SubscriptionCheckout) -> str:
        session = await self.client.checkout_sessions.retrieve(row.provider_session_id)
        if session.payment_id and session.payment_status not in ("failed", "cancelled"):
            return "processing"
        if utcnow() >= session.created_at + timedelta(hours=24, minutes=1):
            return "expired"
        return "open"

    async def checkout_one_time(self, user: User, *, name: str, amount_aed: float, product_id: str | None,
                                metadata: dict[str, str]) -> str:
        if not product_id:
            raise AppError("billing_not_configured", f"{name} isn't available for online payment yet.", 503)
        try:
            product = await self.client.products.retrieve(product_id)
        except Exception:
            raise AppError("billing_preparation_unavailable", "We could not verify this credit pack's payment price. Please try again later.", 503) from None
        price = product.price
        # A media-credit pack is a fixed one-time AED purchase. Never use a
        # recurring product, another currency, or a flexible minimum price.
        if (getattr(product, "is_recurring", True) or price.type != "one_time_price"
                or getattr(price, "price", None) != int(Decimal(str(amount_aed)) * 100)
                or str(getattr(price, "currency", "")).lower() != "aed"
                or getattr(price, "pay_what_you_want", False)):
            raise AppError("billing_price_mismatch", "This credit pack's payment price is being updated. Please try again later.", 503)
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


async def start_checkout(db: AsyncSession, user: User, plan_code: str, interval: str, coupon_code: str | None = None) -> str:
    await lock_plan_changes(db, user.id)
    pending = await pending_checkout(db, user.id, reconcile_expiry=True)
    recovering = pending is not None
    if pending and pending.checkout_url:
        return pending.checkout_url
    if pending and pending.provider != "stripe":
        raise AppError("checkout_in_progress", "Your checkout is being confirmed. Check billing or contact support before trying another payment.", 409)
    if pending and pending.expires_at <= utcnow():
        raise AppError("checkout_in_progress", "An earlier checkout still needs confirmation. Contact support before starting another payment.", 409)
    plan = await db.get(Plan, plan_code)
    if plan is None or not plan.active or plan.code == "free":
        raise AppError("bad_request", "Unknown plan", 400)
    if interval not in ("month", "year"):
        raise AppError("bad_request", "Interval must be month or year", 400)
    sub = await active_subscription(db, user.id)
    if (sub and sub.provider != "trial") or await manageable_online_subscription(db, user.id):
        raise AppError("subscription_exists", "You already have a subscription. Manage it in billing before starting another checkout.", 409)
    if pending:
        # Recover the same Stripe operation after an interrupted response. Its
        # stored plan, coupon and expiry are also part of the idempotency body.
        plan = await db.get(Plan, pending.plan_code)
        interval, coupon_code = pending.interval, pending.coupon_code
        provider = await get_provider(pending.provider)
    else:
        provider = await get_provider()
        now = utcnow()
        pending = SubscriptionCheckout(id=uuid.uuid4(), user_id=user.id, provider=provider.name,
            plan_code=plan.code, interval=interval, coupon_code=coupon_code.strip() if coupon_code else None,
            status="creating", created_at=now, updated_at=now,
            expires_at=now + timedelta(hours=1 if provider.name == "stripe" else 24))
        db.add(pending)
        # Survive process exit or a lost provider response. Another request
        # cannot create a new operation while this reservation exists.
        await db.commit()
    customer_id = sub.provider_customer_id if sub and sub.provider == provider.name else None
    remote_created = False
    try:
        result = await provider.checkout(user, plan, interval, customer_id,
                                         coupon_code=pending.coupon_code, reservation=pending)
        remote_created = isinstance(result, CreatedCheckout)
        if not isinstance(result, CreatedCheckout) or not result.id or not result.url or not result.expires_at:
            raise ValueError("provider_checkout_incomplete")
        await lock_plan_changes(db, user.id)
        row = await db.get(SubscriptionCheckout, pending.id, populate_existing=True)
        if row is None:
            raise AppError("checkout_unavailable", "Your checkout needs support review. Please do not submit another payment.", 503)
        row.provider_session_id, row.checkout_url, row.expires_at = result.id, result.url, result.expires_at
        if row.status == "creating":
            row.status = "open"
        await db.commit()
        return result.url
    except Exception as exc:
        status = getattr(exc, "status_code", getattr(exc, "http_status", None))
        await db.rollback()
        await lock_plan_changes(db, user.id)
        row = await db.get(SubscriptionCheckout, pending.id, populate_existing=True)
        if row and row.status == "creating" and not remote_created and not recovering and (
            isinstance(exc, AppError) or (status in (400, 401, 403, 404, 422) and type(exc).__name__ != "IdempotencyError")
        ):
            row.status = "failed"  # definitive rejection before session creation
        await db.commit()
        if coupon_code and status == 400:
            raise AppError("invalid_coupon", "This coupon couldn't be applied to this plan. Check its expiry and eligibility.", 422) from None
        if isinstance(exc, AppError):
            raise
        raise AppError("checkout_unavailable", "We could not confirm your checkout. Open billing to resume it; please do not submit another payment.", 503) from None


async def lock_plan_changes(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:id, 1))"), {"id": str(user_id)})


async def pending_checkout(db: AsyncSession, user_id: uuid.UUID, *, reconcile_expiry: bool = False) -> SubscriptionCheckout | None:
    row = (await db.execute(select(SubscriptionCheckout).where(
        SubscriptionCheckout.user_id == user_id, SubscriptionCheckout.status.in_(PENDING_CHECKOUT_STATUSES))
        .order_by(SubscriptionCheckout.created_at.desc()))).scalars().first()
    if row and reconcile_expiry and row.expires_at <= utcnow() and row.provider_session_id:
        provider = await get_provider(row.provider)
        try:
            state = await provider.checkout_state(row)
        except Exception:
            raise AppError("checkout_reconciliation_unavailable", "We could not confirm checkout expiry. Resume billing later before starting another payment.", 503) from None
        if state == "expired":
            row.status = "expired"
            await db.flush()
            return None
        row.status = state
    return row


async def cancel_pending_checkout(db: AsyncSession, user_id: uuid.UUID) -> None:
    await lock_plan_changes(db, user_id)
    row = await pending_checkout(db, user_id, reconcile_expiry=True)
    if row is None:
        await db.commit()
        return
    if not row.provider_session_id:
        raise AppError("checkout_in_progress", "Checkout creation is still being confirmed. Contact support before starting another payment.", 409)
    provider = await get_provider(row.provider)
    try:
        state = await provider.checkout_state(row)
        if state == "expired":
            row.status = "expired"
        elif row.provider == "stripe" and state == "open":
            await provider.expire_checkout(row)
            row.status = "expired"
        else:
            raise AppError("checkout_not_cancellable", "This checkout cannot be closed yet. Resume the same checkout or wait for its payment confirmation or expiry.", 409)
    except AppError:
        raise
    except Exception:
        # An expired API response may be lost after the provider succeeds.
        # Retain the hold and reconcile it on the next attempt.
        raise AppError("checkout_reconciliation_unavailable", "We could not confirm checkout closure. Resume billing later before starting another payment.", 503) from None
    await db.commit()


async def manageable_online_subscription(db: AsyncSession, user_id: uuid.UUID) -> Subscription | None:
    """Payment recovery must remain reachable even when paid access has ended."""
    return (await db.execute(select(Subscription).where(
        Subscription.user_id == user_id, Subscription.provider.in_(("stripe", "dodo")),
        Subscription.status.in_(("active", "trialing", "past_due", "unpaid", "incomplete", "pending", "paused")))
        .order_by(Subscription.created_at.desc()))).scalars().first()


async def open_portal(db: AsyncSession, user: User) -> str:
    sub = await manageable_online_subscription(db, user.id)
    if not sub or sub.provider not in ("stripe", "dodo") or not sub.provider_customer_id:
        raise AppError("no_subscription", "You don't have an online subscription to manage.", 404)
    return await (await get_provider(sub.provider)).portal(sub.provider_customer_id)


async def cancel_subscription(db: AsyncSession, user: User) -> Subscription:
    sub = await manageable_online_subscription(db, user.id) or await active_subscription(db, user.id)
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

    await lock_plan_changes(db, user_id)
    if await pending_checkout(db, user_id, reconcile_expiry=True) or await manageable_online_subscription(db, user_id):
        raise AppError("paid_subscription", "Cancel the existing online subscription with its provider before granting manual access.", 409)
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


async def settle_checkout(db: AsyncSession, provider: str, metadata: dict, status: str,
                          *, provider_session_id: str | None = None) -> None:
    """Only signed webhook handlers release or settle a checkout reservation."""
    ident = metadata.get("clastio_checkout_id")
    if ident:
        try:
            condition = SubscriptionCheckout.id == uuid.UUID(ident)
        except (ValueError, TypeError):
            return
    elif provider_session_id:
        condition = SubscriptionCheckout.provider_session_id == provider_session_id
    else:
        return
    row = (await db.execute(select(SubscriptionCheckout).where(
        SubscriptionCheckout.provider == provider, condition))).scalars().first()
    if row:
        await lock_plan_changes(db, row.user_id)
        await db.refresh(row)
        if row.status in PENDING_CHECKOUT_STATUSES:
            row.status = status


async def _record_paid_payment(db: AsyncSession, *, user_id: uuid.UUID, provider: str, ref: str,
                               amount: float, currency: str, tax_amount: float = 0,
                               invoice_url: str | None = None) -> bool:
    """A recovered payment replaces its failed state and emits its receipt once."""
    row = (await db.execute(select(Payment).where(Payment.provider_ref == ref))).scalars().first()
    if row is not None and row.status == "paid":
        return False
    if row is None:
        row = Payment(user_id=user_id, provider=provider, provider_ref=ref)
        db.add(row)
    elif row.user_id != user_id or row.provider != provider:
        raise AppError("payment_reference_conflict", "Payment reference belongs to a different account.", 409)
    row.amount, row.currency, row.tax_amount = amount, currency, tax_amount
    row.status, row.failure_reason = "paid", None
    row.invoice_url = invoice_url or row.invoice_url
    return True


async def handle_stripe_event(db: AsyncSession, event: dict[str, Any]) -> str:
    """Apply one verified Stripe event. Bookkeeping (idempotency, status, retries) is done by process_webhook."""
    obj = event["data"]["object"]
    etype = event["type"]
    changes = _SubChanges()
    result = "processed"
    if etype in ("checkout.session.expired", "checkout.session.async_payment_failed"):
        await settle_checkout(db, "stripe", obj.get("metadata") or {},
            "expired" if etype == "checkout.session.expired" else "failed", provider_session_id=obj.get("id"))
    elif etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded") and obj.get("mode") == "payment" and obj.get("payment_status") == "paid":
        meta = obj.get("metadata") or {}
        if meta.get("kind") == "media_pack" and meta.get("user_id"):
            user_id = uuid.UUID(meta["user_id"])
            await grant_media_pack(db, user_id, meta.get("pack_code", ""), f"stripe:{obj['id']}")
            if await _record_paid_payment(db, user_id=user_id, provider="stripe", ref=obj["id"],
                    amount=(obj.get("amount_total") or 0) / 100, currency=(obj.get("currency") or "aed").upper(),
                    tax_amount=((obj.get("total_details") or {}).get("amount_tax") or 0) / 100):
                await _receipt(db, user_id, obj["id"], (obj.get("amount_total") or 0) / 100,
                               (obj.get("currency") or "aed").upper())
    elif etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded") and obj.get("mode") == "subscription":
        if obj.get("payment_status") not in ("paid", "no_payment_required"):
            # Delayed payment methods can complete checkout before settlement.
            # Subscription/payment webhooks grant access when it is confirmed.
            await settle_checkout(db, "stripe", obj.get("metadata") or {}, "processing", provider_session_id=obj.get("id"))
            return "ignored"
        meta = obj.get("metadata") or {}
        await settle_checkout(db, "stripe", meta, "completed", provider_session_id=obj.get("id"))
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
            sub.status = {"incomplete_expired": "canceled"}.get(status, status)
            if etype == "customer.subscription.deleted":
                sub.status = "canceled"
            if sub.status in ("active", "trialing"):
                await settle_checkout(db, "stripe", meta, "completed")
            elif sub.status == "canceled":
                await settle_checkout(db, "stripe", meta, "failed")
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
        if user_id:
            tax = sum((t.get("amount") or 0) for t in (obj.get("total_taxes") or obj.get("total_tax_amounts") or []))
            newly_paid = await _record_paid_payment(db, user_id=user_id, provider="stripe", ref=obj["id"],
                amount=(obj.get("amount_paid") or 0) / 100, currency=(obj.get("currency") or "aed").upper(),
                tax_amount=tax / 100, invoice_url=obj.get("hosted_invoice_url"))
        else:
            newly_paid = False
        if newly_paid:
            await _receipt(db, user_id, obj["id"], (obj.get("amount_paid") or 0) / 100,
                           (obj.get("currency") or "aed").upper())
            if (obj.get("amount_paid") or 0) > 0:
                from app.services.engagement import reward_referral
                await reward_referral(db, user_id)
        if sub and sub.status in ("past_due", "incomplete", "unpaid"):
            changes.see(sub)
            sub.status = "active"
    elif etype == "invoice.payment_failed":
        sub = await _find_sub(db, obj.get("subscription"))
        if sub:
            changes.see(sub)
            sub.status = "past_due" if sub.status in ("active", "trialing", "past_due") else "incomplete"
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

DODO_STATUS = {"active": "active", "on_hold": "past_due", "past_due": "past_due", "paused": "paused",
               "pending": "pending", "cancelled": "canceled", "failed": "canceled", "expired": "canceled"}


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
            if status == "past_due" and sub.status not in ("active", "trialing", "past_due"):
                status = "pending"
            if etype in ("subscription.cancelled", "subscription.expired", "subscription.failed"):
                status = "canceled"
            if status == "active":  # one active plan per teacher
                await settle_checkout(db, "dodo", meta, "completed")
                for old in (await db.execute(select(Subscription).where(
                        Subscription.user_id == sub.user_id, Subscription.status.in_(("active", "trialing")))
                        )).scalars().all():
                    if old.id != sub.id:
                        changes.see(old)
                        old.status = "canceled"
            sub.status = status
            if status == "canceled":
                await settle_checkout(db, "dodo", meta, "failed")
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
        if data.get("subscription_id") or meta.get("kind") == "subscription":
            # Payment can arrive before subscription.active. Keep the hold
            # until an actual subscription exists, so neither another payment
            # nor a trial/license can overlap this confirmed purchase.
            await settle_checkout(db, "dodo", meta, "completed" if sub else "processing")
        if user_id and payment_id:
            pack_code = meta.get("pack_code") if meta.get("kind") == "media_pack" else None
            if not pack_code:  # metadata missing: fall back to the product bought
                pack_ids = {p.get("dodo_product_id"): p["code"] for p in (await get_setting("media")).get("packs", [])
                            if p.get("dodo_product_id")}
                pack_code = next((pack_ids[i.get("product_id")] for i in data.get("product_cart") or []
                                  if i.get("product_id") in pack_ids), None)
            if pack_code:
                await grant_media_pack(db, user_id, pack_code, f"dodo:{payment_id}")
            if await _record_paid_payment(db, user_id=user_id, provider="dodo", ref=payment_id,
                    amount=(data.get("total_amount") or 0) / 100, currency=(data.get("currency") or "AED").upper(),
                    tax_amount=(data.get("tax") or 0) / 100, invoice_url=data.get("invoice_url")):
                await _receipt(db, user_id, payment_id, (data.get("total_amount") or 0) / 100,
                               (data.get("currency") or "AED").upper())
                if data.get("subscription_id") and not pack_code and (data.get("total_amount") or 0) > 0:
                    from app.services.engagement import reward_referral
                    await reward_referral(db, user_id)
        if sub and sub.status in ("past_due", "pending"):
            changes.see(sub)
            sub.status = "active"
    elif etype == "payment.failed":
        sub = await _find_sub(db, data.get("subscription_id"))
        user_id = sub.user_id if sub else (uuid.UUID(meta["user_id"]) if meta.get("user_id") else None)
        if sub:
            changes.see(sub)
            sub.status = "past_due" if sub.status in ("active", "trialing", "past_due") else "pending"
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
