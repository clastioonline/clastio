"""Durable teacher feedback, separate from generated content and episodic memory."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utcnow, uuid7


class SlideFeedback(Base):
    __tablename__ = "slide_feedback"
    __table_args__ = (UniqueConstraint("slide_id", "version", "kind", name="uq_slide_feedback_slide_id_version_kind"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    slide_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("slides.id", ondelete="CASCADE"))
    version: Mapped[int]
    kind: Mapped[str] = mapped_column(String(20))
    before: Mapped[dict[str, Any]] = mapped_column(JSONB)
    after: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reflected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
