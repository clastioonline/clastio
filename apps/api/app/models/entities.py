"""Database schema. One module keeps foreign keys and relationships easy to audit."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.core.db import Base, TimestampMixin, uuid7

EMBED_DIM = get_settings().embedding_dim


def hnsw_index(table: str) -> Index:
    """Approximate-nearest-neighbour index for cosine-distance search over `embedding`."""
    return Index(f"ix_{table}_embedding_hnsw", "embedding", postgresql_using="hnsw",
                 postgresql_ops={"embedding": "vector_cosine_ops"})


def pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)


def fk(target: str, *, nullable: bool = False, ondelete: str = "CASCADE", index: bool = True):
    return mapped_column(
        UUID(as_uuid=True), ForeignKey(target, ondelete=ondelete), nullable=nullable, index=index
    )


# --------------------------------------------------------------------------- identity


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = pk()
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="school")  # school | department
    country: Mapped[str | None] = mapped_column(String(2))
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[str] = mapped_column(String(20), default="teacher")  # teacher | admin
    # Staff permissions come from this role (see app/core/permissions.py); None for teachers.
    admin_role: Mapped[str | None] = mapped_column(String(20))
    # active | suspended | banned | pending_deletion | deleted  ("email_unverified" is derived from email_verified)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    locale: Mapped[str] = mapped_column(String(10), default="en")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Dubai")
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    phone: Mapped[str | None] = mapped_column(String(20))
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signup_source: Mapped[str | None] = mapped_column(String(40))  # web | google | microsoft | admin
    signup_meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # utm_*, referrer, landing page
    referral_code: Mapped[str | None] = mapped_column(String(16), unique=True)
    referred_by_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True, ondelete="SET NULL", index=False)
    suspended_reason: Mapped[str | None] = mapped_column(String(500))
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    org_id: Mapped[uuid.UUID | None] = fk("organizations.id", nullable=True, ondelete="SET NULL")

    profile: Mapped[TeacherProfile | None] = relationship(back_populates="user", uselist=False,
                                                          foreign_keys="TeacherProfile.user_id")


class OrgMembership(TimestampMixin, Base):
    __tablename__ = "org_memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id"),)
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = fk("organizations.id")
    user_id: Mapped[uuid.UUID] = fk("users.id")
    role: Mapped[str] = mapped_column(String(30), default="teacher")  # school_admin | head_of_department | teacher


class OAuthAccount(TimestampMixin, Base):
    __tablename__ = "oauth_accounts"
    __table_args__ = (UniqueConstraint("provider", "subject"),)
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    provider: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(255))


class Consent(TimestampMixin, Base):
    __tablename__ = "consents"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    # terms | privacy | acceptable_use | cookie | marketing_email | marketing_sms | marketing_whatsapp | whatsapp
    kind: Mapped[str] = mapped_column(String(50), index=True)
    granted: Mapped[bool] = mapped_column(Boolean)
    version: Mapped[str] = mapped_column(String(20), default="1")
    document_id: Mapped[uuid.UUID | None] = fk("legal_documents.id", nullable=True, ondelete="SET NULL", index=False)
    method: Mapped[str | None] = mapped_column(String(40))  # signup_checkbox | reacceptance_modal | settings | banner
    source: Mapped[str | None] = mapped_column(String(40))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = pk()
    actor_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True, ondelete="SET NULL")
    action: Mapped[str] = mapped_column(String(100), index=True)
    target: Mapped[str | None] = mapped_column(String(200), index=True)  # target user id where there is one
    target_type: Mapped[str | None] = mapped_column(String(40))
    target_id: Mapped[str | None] = mapped_column(String(200))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(String(500))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    request_id: Mapped[str | None] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: _now(), index=True)


def _now() -> datetime:
    from app.core.db import utcnow

    return utcnow()


# --------------------------------------------------------------------------- teacher


class TeacherProfile(TimestampMixin, Base):
    __tablename__ = "teacher_profiles"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    country: Mapped[str] = mapped_column(String(2), default="AE")
    region: Mapped[str | None] = mapped_column(String(100))  # emirate / state
    school_name: Mapped[str | None] = mapped_column(String(200))
    curriculum: Mapped[str] = mapped_column(String(40), default="british")
    subjects: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    grades: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    teaching_languages: Mapped[list[str]] = mapped_column(ARRAY(String), default=lambda: ["en"])
    class_duration_minutes: Mapped[int] = mapped_column(Integer, default=45)
    classes_per_day: Mapped[int] = mapped_column(Integer, default=5)
    working_days: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=lambda: [0, 1, 2, 3, 4])
    teaching_style: Mapped[str | None] = mapped_column(Text)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    default_template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    metadata_policy: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    user: Mapped[User] = relationship(back_populates="profile")


class TeacherPreference(TimestampMixin, Base):
    __tablename__ = "teacher_preferences"
    __table_args__ = (UniqueConstraint("user_id", "key"),)
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    key: Mapped[str] = mapped_column(String(80))
    value: Mapped[Any] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(20), default="stated")  # stated | inferred
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=True)


class TeacherMemory(TimestampMixin, Base):
    __tablename__ = "teacher_memory"
    __table_args__ = (hnsw_index("teacher_memory"),)
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    kind: Mapped[str] = mapped_column(String(40))  # lesson_summary | misconception | feedback | note | chat_summary
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    class_section_id: Mapped[uuid.UUID | None] = fk("class_sections.id", nullable=True, ondelete="SET NULL")
    lesson_id: Mapped[uuid.UUID | None] = fk("lessons.id", nullable=True, ondelete="SET NULL")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))


class ClassSection(TimestampMixin, Base):
    __tablename__ = "class_sections"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    name: Mapped[str] = mapped_column(String(60))  # e.g. "8A"
    grade: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(80))
    curriculum: Mapped[str | None] = mapped_column(String(40))
    pace: Mapped[str] = mapped_column(String(20), default="standard")  # slower | standard | faster
    ability_mix: Mapped[str] = mapped_column(String(40), default="mixed")
    eal_percent: Mapped[int] = mapped_column(Integer, default=0)
    send_notes: Mapped[str | None] = mapped_column(Text)  # aggregate, no student names
    notes: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(9), default="#2563EB")
    active_course_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class TimetableSlot(TimestampMixin, Base):
    __tablename__ = "timetable_slots"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    class_section_id: Mapped[uuid.UUID] = fk("class_sections.id")
    day_of_week: Mapped[int] = mapped_column(Integer)  # 0 = Monday
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    room: Mapped[str | None] = mapped_column(String(60))


class CalendarEvent(TimestampMixin, Base):
    __tablename__ = "calendar_events"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    org_id: Mapped[uuid.UUID | None] = fk("organizations.id", nullable=True)
    kind: Mapped[str] = mapped_column(String(20))  # holiday | ramadan | exam | short_day | term | event
    title: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date)
    duration_factor: Mapped[float] = mapped_column(Float, default=1.0)  # e.g. 0.75 during Ramadan


# --------------------------------------------------------------------------- curriculum


class CurriculumFramework(Base):
    __tablename__ = "curriculum_frameworks"
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    country: Mapped[str | None] = mapped_column(String(2))
    grade_labels: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class LearningOutcome(TimestampMixin, Base):
    __tablename__ = "learning_outcomes"
    __table_args__ = (Index("ix_outcomes_lookup", "framework_code", "subject", "grade"), hnsw_index("learning_outcomes"))
    id: Mapped[uuid.UUID] = pk()
    framework_code: Mapped[str] = mapped_column(ForeignKey("curriculum_frameworks.code", ondelete="CASCADE"))
    owner_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)  # custom outcomes
    subject: Mapped[str] = mapped_column(String(80))
    grade: Mapped[str] = mapped_column(String(20))
    strand: Mapped[str | None] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(60))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))


# --------------------------------------------------------------------------- files, styles, templates


class UploadedFile(TimestampMixin, Base):
    __tablename__ = "uploaded_files"
    __table_args__ = (Index("ix_uploaded_owner_sha", "owner_id", "sha256"),)
    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID] = fk("users.id")
    filename: Mapped[str] = mapped_column(String(300))
    mime: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20), default="style")  # style | source
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default="uploaded")
    stage: Mapped[str | None] = mapped_column(String(60))
    error: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    content_rights_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class SourceChunk(Base):
    __tablename__ = "source_chunks"
    __table_args__ = (hnsw_index("source_chunks"),)
    id: Mapped[uuid.UUID] = pk()
    file_id: Mapped[uuid.UUID] = fk("uploaded_files.id")
    owner_id: Mapped[uuid.UUID] = fk("users.id")
    page: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))


class StyleProfile(TimestampMixin, Base):
    __tablename__ = "style_profiles"
    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID] = fk("users.id")
    source_file_id: Mapped[uuid.UUID | None] = fk("uploaded_files.id", nullable=True, ondelete="SET NULL")
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1)
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    overrides: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Template(TimestampMixin, Base):
    __tablename__ = "templates"
    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)  # None = built-in
    org_id: Mapped[uuid.UUID | None] = fk("organizations.id", nullable=True)
    style_profile_id: Mapped[uuid.UUID | None] = fk("style_profiles.id", nullable=True, ondelete="SET NULL")
    name: Mapped[str] = mapped_column(String(200))
    mode: Mapped[str] = mapped_column(String(20))  # native | reconstructed | builtin
    status: Mapped[str] = mapped_column(String(20), default="ready")
    base_storage_key: Mapped[str] = mapped_column(String(500))
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # TemplateSpec
    preview_keys: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    subject: Mapped[str | None] = mapped_column(String(80))
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)


# --------------------------------------------------------------------------- projects & lessons


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_owner_created", "owner_id", "created_at"),)
    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID] = fk("users.id")
    title: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(20), default="course")
    status: Mapped[str] = mapped_column(String(30), default="draft")
    class_section_id: Mapped[uuid.UUID | None] = fk("class_sections.id", nullable=True, ondelete="SET NULL")


class Course(TimestampMixin, Base):
    __tablename__ = "courses"
    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = fk("projects.id")
    owner_id: Mapped[uuid.UUID] = fk("users.id")
    topic: Mapped[str] = mapped_column(String(300))
    subject: Mapped[str] = mapped_column(String(80))
    grade: Mapped[str] = mapped_column(String(20))
    curriculum: Mapped[str] = mapped_column(String(40))
    language: Mapped[str] = mapped_column(String(10), default="en")
    num_lectures: Mapped[int] = mapped_column(Integer)
    slides_per_lecture: Mapped[int] = mapped_column(Integer)
    lecture_minutes: Mapped[int] = mapped_column(Integer, default=45)
    template_id: Mapped[uuid.UUID | None] = fk("templates.id", nullable=True, ondelete="SET NULL")
    class_section_id: Mapped[uuid.UUID | None] = fk("class_sections.id", nullable=True, ondelete="SET NULL")
    outcome_codes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    options: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    plan: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    error: Mapped[str | None] = mapped_column(Text)


class Lesson(TimestampMixin, Base):
    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("course_id", "number"),)
    id: Mapped[uuid.UUID] = pk()
    course_id: Mapped[uuid.UUID] = fk("courses.id")
    owner_id: Mapped[uuid.UUID] = fk("users.id")
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    plan: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="planned")
    scheduled_date: Mapped[date | None] = mapped_column(Date, index=True)
    taught_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pptx_key: Mapped[str | None] = mapped_column(String(500))
    pdf_key: Mapped[str | None] = mapped_column(String(500))
    qc_report: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    carry_over: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class Slide(TimestampMixin, Base):
    __tablename__ = "slides"
    __table_args__ = (UniqueConstraint("lesson_id", "number"),)
    id: Mapped[uuid.UUID] = pk()
    lesson_id: Mapped[uuid.UUID] = fk("lessons.id")
    number: Mapped[int] = mapped_column(Integer)
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB)
    qc: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    preview_key: Mapped[str | None] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, default=1)


class SlideVersion(Base):
    __tablename__ = "slide_versions"
    id: Mapped[uuid.UUID] = pk()
    slide_id: Mapped[uuid.UUID] = fk("slides.id")
    version: Mapped[int] = mapped_column(Integer)
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: _now())


class LessonReflection(TimestampMixin, Base):
    __tablename__ = "lesson_reflections"
    id: Mapped[uuid.UUID] = pk()
    lesson_id: Mapped[uuid.UUID] = fk("lessons.id")
    owner_id: Mapped[uuid.UUID] = fk("users.id")
    outcome: Mapped[str] = mapped_column(String(30))  # went_well | ran_out_of_time | struggled | skipped
    note: Mapped[str | None] = mapped_column(Text)
    covered_until_slide: Mapped[int | None] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(20), default="web")


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (hnsw_index("assets"),)
    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    kind: Mapped[str] = mapped_column(String(20))  # image | icon | diagram
    prompt: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(40))  # upload | openverse | ai | placeholder
    license: Mapped[str | None] = mapped_column(String(120))
    attribution: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))


class Document(TimestampMixin, Base):
    """Worksheets, quizzes, homework, assessments, lesson-plan and teacher-guide documents."""

    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_owner_created", "owner_id", "created_at"),)
    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID] = fk("users.id")
    course_id: Mapped[uuid.UUID | None] = fk("courses.id", nullable=True)
    lesson_id: Mapped[uuid.UUID | None] = fk("lessons.id", nullable=True)
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(300))
    difficulty: Mapped[str | None] = mapped_column(String(20))
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    files: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # {"docx": key, "pdf": key, ...}
    status: Mapped[str] = mapped_column(String(20), default="queued")


class Question(TimestampMixin, Base):
    __tablename__ = "questions"
    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID] = fk("users.id")
    course_id: Mapped[uuid.UUID | None] = fk("courses.id", nullable=True)
    lesson_id: Mapped[uuid.UUID | None] = fk("lessons.id", nullable=True)
    class_section_id: Mapped[uuid.UUID | None] = fk("class_sections.id", nullable=True, ondelete="SET NULL")
    qtype: Mapped[str] = mapped_column(String(30))
    difficulty: Mapped[str] = mapped_column(String(10), default="medium")
    bloom: Mapped[str | None] = mapped_column(String(20))
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[list[str]] = mapped_column(JSONB, default=list)
    answer: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    outcome_codes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    used_count: Mapped[int] = mapped_column(Integer, default=0)


# --------------------------------------------------------------------------- assistant


class Conversation(TimestampMixin, Base):
    __tablename__ = "assistant_conversations"
    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID] = fk("users.id")
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    channel: Mapped[str] = mapped_column(String(20), default="web")


class ConversationMessage(Base):
    __tablename__ = "assistant_messages"
    id: Mapped[uuid.UUID] = pk()
    conversation_id: Mapped[uuid.UUID] = fk("assistant_conversations.id")
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    actions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: _now())


# --------------------------------------------------------------------------- jobs & usage


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        Index("ix_jobs_pending", "status", "run_after", postgresql_where="status = 'queued'"),
        Index("ix_jobs_owner_created", "owner_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    parent_id: Mapped[uuid.UUID | None] = fk("generation_jobs.id", nullable=True, ondelete="SET NULL")
    type: Mapped[str] = mapped_column(String(40))
    queue: Mapped[str] = mapped_column(String(20), default="default")
    status: Mapped[str] = mapped_column(String(20), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str | None] = mapped_column(String(120))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    input_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: _now())
    locked_by: Mapped[str | None] = mapped_column(String(100))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    credits_reserved: Mapped[int] = mapped_column(Integer, default=0)  # counted against limits while running
    # The owner's plan limit on jobs running at once (the worker won't start more than this for one teacher).
    max_concurrent: Mapped[int | None] = mapped_column(Integer)
    request_id: Mapped[str | None] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: _now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIUsage(Base):
    __tablename__ = "ai_usage"
    __table_args__ = (Index("ix_ai_usage_owner_created", "owner_id", "created_at"),)
    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True, ondelete="SET NULL")
    job_id: Mapped[uuid.UUID | None] = fk("generation_jobs.id", nullable=True, ondelete="SET NULL")
    task: Mapped[str] = mapped_column(String(60))
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str | None] = mapped_column(String(40))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0)
    images: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    request_id: Mapped[str | None] = mapped_column(String(40), index=True)
    error_code: Mapped[str | None] = mapped_column(String(60))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: _now(), index=True)


class AppSetting(Base):
    """Admin-editable runtime configuration (model routing, credit costs, feature flags)."""

    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: _now())


# --------------------------------------------------------------------------- billing


class Plan(Base):
    __tablename__ = "plans"
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    price_monthly_aed: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    price_annual_aed: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    limits: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    features: Mapped[list[str]] = mapped_column(JSONB, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    plan_code: Mapped[str] = mapped_column(ForeignKey("plans.code"))
    status: Mapped[str] = mapped_column(String(20), default="active")  # trialing|active|past_due|canceled
    interval: Mapped[str] = mapped_column(String(10), default="month")
    provider: Mapped[str] = mapped_column(String(20), default="none")
    provider_customer_id: Mapped[str | None] = mapped_column(String(120))
    provider_subscription_id: Mapped[str | None] = mapped_column(String(120), index=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price_aed: Mapped[float | None] = mapped_column(Numeric(12, 2))


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    provider: Mapped[str] = mapped_column(String(20))
    provider_ref: Mapped[str] = mapped_column(String(120), unique=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="AED")
    tax_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(20))  # paid | failed | refunded
    invoice_url: Mapped[str | None] = mapped_column(String(500))
    invoice_id: Mapped[str | None] = mapped_column(String(120))
    subscription_ref: Mapped[str | None] = mapped_column(String(120))
    failure_reason: Mapped[str | None] = mapped_column(String(500))


class CreditLedger(Base):
    __tablename__ = "credit_ledger"
    __table_args__ = (Index("ix_credit_owner_created", "owner_id", "created_at"),)
    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID] = fk("users.id")
    amount: Mapped[int] = mapped_column(Integer)  # negative = spend, positive = grant/refund
    resource: Mapped[str] = mapped_column(String(30))  # credits | media_credits | whatsapp_messages | ai_images
    # CREDIT_USAGE | CREDIT_REFUND | CREDIT_PURCHASE | CREDIT_ADMIN_GRANT | CREDIT_ADJUSTMENT | CREDIT_EXPIRATION
    event_type: Mapped[str] = mapped_column(String(30), default="CREDIT_USAGE")
    reason: Mapped[str] = mapped_column(String(80))
    ref: Mapped[str | None] = mapped_column(String(120), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(40))
    resource_id: Mapped[str | None] = mapped_column(String(80))
    provider_cost_usd: Mapped[float | None] = mapped_column(Float)
    actor_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True, ondelete="SET NULL", index=False)
    request_id: Mapped[str | None] = mapped_column(String(40), index=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: _now())


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("provider", "event_id"),)
    id: Mapped[uuid.UUID] = pk()
    provider: Mapped[str] = mapped_column(String(20))
    event_id: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    payload_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="received")  # received | processed | failed | ignored
    result: Mapped[str | None] = mapped_column(String(40))
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: _now())


class MediaItem(TimestampMixin, Base):
    """An AI-generated image or video from the media studio. Always labelled as AI-generated."""

    __tablename__ = "media_items"
    __table_args__ = (Index("ix_media_owner_created", "owner_id", "created_at"),)
    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID] = fk("users.id")
    kind: Mapped[str] = mapped_column(String(10))  # image | video
    prompt: Mapped[str] = mapped_column(Text)
    style: Mapped[str | None] = mapped_column(String(60))
    aspect: Mapped[str] = mapped_column(String(10), default="16:9")
    seconds: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued | running | ready | failed
    credits: Mapped[int] = mapped_column(Integer, default=0)
    provider: Mapped[str | None] = mapped_column(String(20))
    model: Mapped[str | None] = mapped_column(String(80))
    mime_type: Mapped[str | None] = mapped_column(String(60))
    storage_key: Mapped[str | None] = mapped_column(String(500))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


# --------------------------------------------------------------------------- WhatsApp


class WhatsAppContact(TimestampMixin, Base):
    __tablename__ = "whatsapp_contacts"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    phone_e164: Mapped[str] = mapped_column(String(20), unique=True)
    verification_code: Mapped[str | None] = mapped_column(String(10))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    opted_in: Mapped[bool] = mapped_column(Boolean, default=False)
    opted_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    daily_time: Mapped[str] = mapped_column(String(5), default="06:45")
    reflection_time: Mapped[str] = mapped_column(String(5), default="15:30")
    quiet_start: Mapped[str] = mapped_column(String(5), default="21:00")
    quiet_end: Mapped[str] = mapped_column(String(5), default="06:00")
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_daily_sent_on: Mapped[date | None] = mapped_column(Date)
    last_reflection_sent_on: Mapped[date | None] = mapped_column(Date)


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"
    __table_args__ = (Index("ix_wa_user_created", "user_id", "created_at"),)
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True, ondelete="SET NULL")
    direction: Mapped[str] = mapped_column(String(10))  # in | out
    wa_message_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    template: Mapped[str | None] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(20), default="service")  # utility | service | marketing
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="queued")
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: _now())


class AICallReservation(Base):
    """Durable admission ledger; unresolved calls keep their full reservation."""
    __tablename__ = "ai_call_reservations"
    id: Mapped[uuid.UUID] = pk()
    owner_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True, ondelete="SET NULL")
    job_id: Mapped[uuid.UUID | None] = fk("generation_jobs.id", nullable=True, ondelete="SET NULL")
    usage_id: Mapped[uuid.UUID | None] = fk("ai_usage.id", nullable=True, ondelete="SET NULL")
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(80))
    task: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    reserved_usd: Mapped[float] = mapped_column(Numeric(18, 8))
    charged_usd: Mapped[float | None] = mapped_column(Numeric(18, 8))
    rates: Mapped[dict[str, Any]] = mapped_column(JSONB)
    usage: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now().astimezone(), index=True)
