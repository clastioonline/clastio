"""Single-use licenses. Plain keys are never persisted."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utcnow, uuid7


class PlanLicense(Base):
    __tablename__ = "plan_licenses"
    __table_args__ = (
        CheckConstraint("months BETWEEN 1 AND 36", name="valid_months"),
        # The original raw-SQL migration uses PostgreSQL's generated name.
        # Keep it here to prevent needless unique-constraint replacement.
        UniqueConstraint("key_hash", name="plan_licenses_key_hash_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    key_hash: Mapped[str] = mapped_column(String(64))
    key_suffix: Mapped[str] = mapped_column(String(8))
    plan_code: Mapped[str] = mapped_column(String(40), ForeignKey("plans.code"))
    months: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    redeemed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
