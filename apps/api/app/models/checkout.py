"""Durable subscription checkout reservations, independent from paid access."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, uuid7


class SubscriptionCheckout(TimestampMixin, Base):
    __tablename__ = "subscription_checkouts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_session_id"),
        Index("ix_subscription_checkouts_pending_user", "user_id", unique=True,
              postgresql_where=text("status IN ('creating', 'open', 'processing')")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(20))
    plan_code: Mapped[str] = mapped_column(String(40), ForeignKey("plans.code"))
    interval: Mapped[str] = mapped_column(String(10))
    coupon_code: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="creating")
    provider_session_id: Mapped[str | None] = mapped_column(String(255))
    checkout_url: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
