"""Durable AI spending reservations."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b174cafe0123"
down_revision = "89c637411250"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ai_call_reservations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("owner_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("job_id", sa.UUID(), sa.ForeignKey("generation_jobs.id", ondelete="SET NULL")),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("task", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reserved_usd", sa.Numeric(18, 8), nullable=False),
        sa.Column("charged_usd", sa.Numeric(18, 8)),
        sa.Column("rates", postgresql.JSONB(), nullable=False),
        sa.Column("usage", postgresql.JSONB(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    for field in ("owner_id", "job_id", "status", "created_at"):
        op.create_index(f"ix_ai_call_reservations_{field}", "ai_call_reservations", [field])


def downgrade():
    op.drop_table("ai_call_reservations")
