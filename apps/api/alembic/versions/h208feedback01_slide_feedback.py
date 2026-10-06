"""Durable, idempotent slide edit and acceptance feedback."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "h208feedback01"
down_revision = "g207credits01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("slide_feedback",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slide_id", sa.UUID(), sa.ForeignKey("slides.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("before", postgresql.JSONB(), nullable=False),
        sa.Column("after", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reflected_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("slide_id", "version", "kind", name="uq_slide_feedback_slide_id_version_kind"))
    op.create_index("ix_slide_feedback_user_id", "slide_feedback", ["user_id"])
    op.create_index("ix_slide_feedback_reflected_at", "slide_feedback", ["reflected_at"])


def downgrade() -> None:
    op.drop_table("slide_feedback")
