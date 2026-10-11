"""Add standalone UAE planners, demo classes, and cached digital resources.

Existing courses, lesson JSON plans, uploads, and conversations remain intact.
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "i209educator01"
down_revision = "h208feedback01"
branch_labels = None
depends_on = None

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


def _identity():
    return [
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("owner_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def _text(name, length, default=None, *, nullable=False):
    return sa.Column(name, sa.String(length), nullable=nullable, server_default=default)


def _integer(name, default):
    return sa.Column(name, sa.Integer(), nullable=False, server_default=str(default))


def _json(name, *, array=False):
    return sa.Column(name, postgresql.JSONB(), nullable=False, server_default="[]" if array else "{}")


def _optional_fk(name, target):
    return sa.Column(name, sa.UUID(), sa.ForeignKey(target, ondelete="SET NULL"), nullable=True)


def _check(table, expression, name):
    return sa.CheckConstraint(expression, name=op.f(f"ck_{table}_{name}"))


def _indexes(table, references=()):
    for column in ("owner_id", "status", *references):
        op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_index(f"ix_{table}_owner_created", table, ["owner_id", "created_at"])


def upgrade() -> None:
    op.add_column("teacher_profiles", _text("regulatory_authority", 20, "not_specified"))
    op.add_column("teacher_profiles", sa.Column("education_stages", postgresql.ARRAY(sa.String()),
                                               nullable=False, server_default="{}"))
    op.add_column("teacher_profiles", _json("planning_preferences"))
    op.create_check_constraint(op.f("ck_teacher_profiles_regulatory_authority"), "teacher_profiles",
                               "regulatory_authority IN ('khda', 'adek', 'moe', 'other', 'not_specified')")
    op.create_check_constraint(op.f("ck_teacher_profiles_education_stages"), "teacher_profiles",
                               "education_stages <@ ARRAY['early_years', 'primary', 'secondary', 'university']::varchar[]")

    table = "lesson_plans"
    op.create_table(table, *_identity(),
        _optional_fk("lesson_id", "lessons.id"),
        _optional_fk("class_section_id", "class_sections.id"),
        _text("title", 300), _text("topic", 300), _text("subject", 80), _text("grade", 30),
        _text("curriculum", 40), _text("language", 10, "en"),
        _text("education_stage", 20, "secondary"), _text("framework", 20, "not_specified"),
        _integer("schema_version", 1), _integer("version", 1), _integer("duration_minutes", 45),
        _text("status", 20, "draft"),
        _json("learning_objectives", array=True), _json("success_criteria", array=True),
        _json("cross_curricular_links", array=True), _json("uae_context"), _json("differentiation"),
        _json("formative_assessment", array=True), _json("lesson_sequence", array=True),
        _json("prerequisites", array=True),
        sa.Column("homework", postgresql.JSONB(), nullable=False, server_default='""'),
        _json("resources", array=True),
        _json("source_references", array=True), _json("review_checks"),
        _text("pdf_key", 500, nullable=True), sa.Column("error", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        _check(table, FRAMEWORK_CHECK, "framework"), _check(table, STAGE_CHECK, "education_stage"),
        _check(table, STATUS_CHECK, "status"), _check(table, "duration_minutes > 0", "duration_positive"),
        _check(table, "version > 0 AND schema_version > 0", "versions_positive"),
        _check(table, READY_PLAN_CHECK, "ready_content"),
        _check(table, "education_stage <> 'university' OR framework IN ('other', 'not_specified')",
               "university_framework"))
    _indexes(table, ("lesson_id", "class_section_id"))

    table = "demo_classes"
    op.create_table(table, *_identity(),
        _optional_fk("lesson_plan_id", "lesson_plans.id"), _optional_fk("lesson_id", "lessons.id"),
        _text("title", 300), _text("topic", 300), _text("subject", 80), _text("grade", 30),
        _text("curriculum", 40), _text("language", 10, "en"), _text("framework", 20, "not_specified"),
        _integer("duration_minutes", 15), _text("status", 20, "draft"), _integer("version", 1),
        _json("hook"), _json("teacher_script", array=True), _json("slide_payload"),
        _json("source_references", array=True), _json("review_checks"),
        _text("pptx_key", 500, nullable=True), _text("pdf_key", 500, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        _check(table, FRAMEWORK_CHECK, "framework"), _check(table, STATUS_CHECK, "status"),
        _check(table, "duration_minutes = 15", "fifteen_minutes"),
        _check(table, "version > 0", "version_positive"),
        _check(table, READY_DEMO_CHECK, "ready_content"))
    _indexes(table, ("lesson_plan_id", "lesson_id"))

    table = "digital_resources"
    op.create_table(table, *_identity(),
        _optional_fk("uploaded_file_id", "uploaded_files.id"), _optional_fk("document_id", "documents.id"),
        _text("title", 300), _text("topic", 300), _text("subject", 80), _text("education_stage", 20),
        _text("grade", 30, nullable=True), _text("curriculum", 40), _text("language", 10, "en"),
        _text("kind", 30), _text("origin", 20), _text("status", 20, "draft"),
        _integer("version", 1), _integer("schema_version", 1), _text("cache_key", 64),
        _json("content"), _json("chapters", array=True), _json("source_references", array=True),
        _json("license_metadata"), _text("pdf_key", 500, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.UniqueConstraint("owner_id", "cache_key", name="uq_digital_resources_owner_cache"),
        _check(table, STAGE_CHECK, "education_stage"), _check(table, STATUS_CHECK, "status"),
        _check(table, "version > 0 AND schema_version > 0", "versions_positive"),
        _check(table, "origin IN ('uploaded', 'official', 'generated')", "origin"),
        _check(table, "kind IN ('book', 'guide', 'subject_primer', 'study_guide')", "kind"),
        _check(table, "origin <> 'generated' OR kind IN ('subject_primer', 'study_guide')", "generated_kind"),
        _check(table, READY_RESOURCE_CHECK, "ready_generated_content"))
    _indexes(table, ("uploaded_file_id", "document_id"))
    op.create_index("ix_digital_resources_lookup", table,
                    ["owner_id", "subject", "education_stage", "curriculum", "language"])


def downgrade() -> None:
    op.drop_table("digital_resources")
    op.drop_table("demo_classes")
    op.drop_table("lesson_plans")
    op.drop_constraint(op.f("ck_teacher_profiles_education_stages"), "teacher_profiles", type_="check")
    op.drop_constraint(op.f("ck_teacher_profiles_regulatory_authority"), "teacher_profiles", type_="check")
    op.drop_column("teacher_profiles", "planning_preferences")
    op.drop_column("teacher_profiles", "education_stages")
    op.drop_column("teacher_profiles", "regulatory_authority")
