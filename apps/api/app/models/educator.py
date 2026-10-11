"""Standalone teacher planners, demonstration classes, and reusable learning resources.

Legacy slide lessons retain their existing JSON plans. A standalone planner may link
to a slide lesson without changing the presentation generator's schema.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, uuid7

FRAMEWORK_CHECK = "framework IN ('khda', 'adek', 'moe', 'other', 'not_specified')"
STAGE_CHECK = "education_stage IN ('early_years', 'primary', 'secondary', 'university')"
STATUS_CHECK = "status IN ('draft', 'queued', 'generating', 'ready', 'reviewed', 'failed', 'archived')"
READY_PLAN_CHECK = """status NOT IN ('ready', 'reviewed') OR (
    jsonb_typeof(learning_objectives) = 'array' AND learning_objectives <> '[]'::jsonb
    AND jsonb_typeof(success_criteria) = 'array' AND success_criteria <> '[]'::jsonb
    AND jsonb_typeof(cross_curricular_links) = 'array' AND cross_curricular_links <> '[]'::jsonb
    AND jsonb_typeof(formative_assessment) = 'array' AND formative_assessment <> '[]'::jsonb
    AND jsonb_typeof(lesson_sequence) = 'array' AND lesson_sequence <> '[]'::jsonb
    AND jsonb_typeof(uae_context) = 'object'
    AND uae_context ?& ARRAY['national_identity', 'moral_education', 'arabic_culture']
    AND jsonb_typeof(uae_context -> 'national_identity') = 'object'
    AND (uae_context -> 'national_identity') <> '{}'::jsonb
    AND jsonb_typeof(uae_context -> 'moral_education') = 'object'
    AND (uae_context -> 'moral_education') <> '{}'::jsonb
    AND jsonb_typeof(uae_context -> 'arabic_culture') = 'object'
    AND (uae_context -> 'arabic_culture') <> '{}'::jsonb
    AND jsonb_typeof(differentiation) = 'object'
    AND differentiation ?& ARRAY['sen', 'ell']
    AND jsonb_typeof(differentiation -> 'sen') = 'array'
    AND (differentiation -> 'sen') <> '[]'::jsonb
    AND jsonb_typeof(differentiation -> 'ell') = 'array'
    AND (differentiation -> 'ell') <> '[]'::jsonb
)"""
READY_DEMO_CHECK = """status NOT IN ('ready', 'reviewed') OR (
    jsonb_typeof(teacher_script) = 'array' AND teacher_script <> '[]'::jsonb
    AND jsonb_typeof(hook) = 'object' AND hook <> '{}'::jsonb
    AND jsonb_typeof(slide_payload) = 'object'
    AND slide_payload ? 'slides'
    AND jsonb_typeof(slide_payload -> 'slides') = 'array'
    AND (slide_payload -> 'slides') <> '[]'::jsonb
)"""
READY_RESOURCE_CHECK = """origin <> 'generated' OR status NOT IN ('ready', 'reviewed') OR (
    jsonb_typeof(content) = 'object' AND content <> '{}'::jsonb
    AND jsonb_typeof(chapters) = 'array' AND chapters <> '[]'::jsonb
)"""


def _pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)


def _fk(target, *, nullable=False, ondelete="CASCADE", index=True):
    return mapped_column(UUID(as_uuid=True), ForeignKey(target, ondelete=ondelete),
                         nullable=nullable, index=index)


def _array():
    return mapped_column(JSONB, default=list, server_default="[]")


def _object():
    return mapped_column(JSONB, default=dict, server_default="{}")


class LessonPlan(TimestampMixin, Base):
    __tablename__ = "lesson_plans"
    __table_args__ = (
        Index("ix_lesson_plans_owner_created", "owner_id", "created_at"),
        CheckConstraint(FRAMEWORK_CHECK, name="framework"),
        CheckConstraint(STAGE_CHECK, name="education_stage"),
        CheckConstraint(STATUS_CHECK, name="status"),
        CheckConstraint("duration_minutes > 0", name="duration_positive"),
        CheckConstraint("version > 0 AND schema_version > 0", name="versions_positive"),
        CheckConstraint(READY_PLAN_CHECK, name="ready_content"),
        CheckConstraint("education_stage <> 'university' OR framework IN ('other', 'not_specified')",
                        name="university_framework"),
    )
    id: Mapped[uuid.UUID] = _pk()
    owner_id: Mapped[uuid.UUID] = _fk("users.id")
    lesson_id: Mapped[uuid.UUID | None] = _fk("lessons.id", nullable=True, ondelete="SET NULL")
    class_section_id: Mapped[uuid.UUID | None] = _fk("class_sections.id", nullable=True, ondelete="SET NULL")
    title: Mapped[str] = mapped_column(String(300))
    topic: Mapped[str] = mapped_column(String(300))
    subject: Mapped[str] = mapped_column(String(80))
    grade: Mapped[str] = mapped_column(String(30))
    curriculum: Mapped[str] = mapped_column(String(40))
    language: Mapped[str] = mapped_column(String(10), default="en", server_default="en")
    education_stage: Mapped[str] = mapped_column(String(20), default="secondary", server_default="secondary")
    framework: Mapped[str] = mapped_column(String(20), default="not_specified", server_default="not_specified")
    schema_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=45, server_default="45")
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft", index=True)
    learning_objectives: Mapped[list[dict[str, Any]]] = _array()
    success_criteria: Mapped[list[dict[str, Any]]] = _array()
    cross_curricular_links: Mapped[list[dict[str, Any]]] = _array()
    uae_context: Mapped[dict[str, Any]] = _object()
    differentiation: Mapped[dict[str, Any]] = _object()
    formative_assessment: Mapped[list[dict[str, Any]]] = _array()
    lesson_sequence: Mapped[list[dict[str, Any]]] = _array()
    prerequisites: Mapped[list[str]] = _array()
    homework: Mapped[str] = mapped_column(JSONB, default="", server_default='""')
    resources: Mapped[list[str]] = _array()
    source_references: Mapped[list[dict[str, Any]]] = _array()
    review_checks: Mapped[dict[str, Any]] = _object()
    pdf_key: Mapped[str | None] = mapped_column(String(500))
    error: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DemoClass(TimestampMixin, Base):
    __tablename__ = "demo_classes"
    __table_args__ = (
        Index("ix_demo_classes_owner_created", "owner_id", "created_at"),
        CheckConstraint(FRAMEWORK_CHECK, name="framework"),
        CheckConstraint(STATUS_CHECK, name="status"),
        CheckConstraint("duration_minutes = 15", name="fifteen_minutes"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(READY_DEMO_CHECK, name="ready_content"),
    )
    id: Mapped[uuid.UUID] = _pk()
    owner_id: Mapped[uuid.UUID] = _fk("users.id")
    lesson_plan_id: Mapped[uuid.UUID | None] = _fk("lesson_plans.id", nullable=True, ondelete="SET NULL")
    lesson_id: Mapped[uuid.UUID | None] = _fk("lessons.id", nullable=True, ondelete="SET NULL")
    title: Mapped[str] = mapped_column(String(300))
    topic: Mapped[str] = mapped_column(String(300))
    subject: Mapped[str] = mapped_column(String(80))
    grade: Mapped[str] = mapped_column(String(30))
    curriculum: Mapped[str] = mapped_column(String(40))
    language: Mapped[str] = mapped_column(String(10), default="en", server_default="en")
    framework: Mapped[str] = mapped_column(String(20), default="not_specified", server_default="not_specified")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=15, server_default="15")
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    hook: Mapped[dict[str, Any]] = _object()
    teacher_script: Mapped[list[dict[str, Any]]] = _array()
    slide_payload: Mapped[dict[str, Any]] = _object()
    source_references: Mapped[list[dict[str, Any]]] = _array()
    review_checks: Mapped[dict[str, Any]] = _object()
    pptx_key: Mapped[str | None] = mapped_column(String(500))
    pdf_key: Mapped[str | None] = mapped_column(String(500))
    error: Mapped[str | None] = mapped_column(Text)


class DigitalResource(TimestampMixin, Base):
    __tablename__ = "digital_resources"
    __table_args__ = (
        Index("ix_digital_resources_owner_created", "owner_id", "created_at"),
        Index("ix_digital_resources_lookup", "owner_id", "subject", "education_stage", "curriculum", "language"),
        UniqueConstraint("owner_id", "cache_key", name="uq_digital_resources_owner_cache"),
        CheckConstraint(STAGE_CHECK, name="education_stage"),
        CheckConstraint(STATUS_CHECK, name="status"),
        CheckConstraint("version > 0 AND schema_version > 0", name="versions_positive"),
        CheckConstraint("origin IN ('uploaded', 'official', 'generated')", name="origin"),
        CheckConstraint("kind IN ('book', 'guide', 'subject_primer', 'study_guide')", name="kind"),
        CheckConstraint("origin <> 'generated' OR kind IN ('subject_primer', 'study_guide')",
                        name="generated_kind"),
        CheckConstraint(READY_RESOURCE_CHECK, name="ready_generated_content"),
    )
    id: Mapped[uuid.UUID] = _pk()
    owner_id: Mapped[uuid.UUID] = _fk("users.id")
    uploaded_file_id: Mapped[uuid.UUID | None] = _fk("uploaded_files.id", nullable=True, ondelete="SET NULL")
    document_id: Mapped[uuid.UUID | None] = _fk("documents.id", nullable=True, ondelete="SET NULL")
    title: Mapped[str] = mapped_column(String(300))
    topic: Mapped[str] = mapped_column(String(300))
    subject: Mapped[str] = mapped_column(String(80))
    education_stage: Mapped[str] = mapped_column(String(20))
    grade: Mapped[str | None] = mapped_column(String(30))
    curriculum: Mapped[str] = mapped_column(String(40))
    language: Mapped[str] = mapped_column(String(10), default="en", server_default="en")
    kind: Mapped[str] = mapped_column(String(30))
    origin: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    schema_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    cache_key: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict[str, Any]] = _object()
    chapters: Mapped[list[dict[str, Any]]] = _array()
    source_references: Mapped[list[dict[str, Any]]] = _array()
    license_metadata: Mapped[dict[str, Any]] = _object()
    pdf_key: Mapped[str | None] = mapped_column(String(500))
    error: Mapped[str | None] = mapped_column(Text)
