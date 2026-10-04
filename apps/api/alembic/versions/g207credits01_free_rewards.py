"""Reviewed credit tasks and signed-browser trial deterrence."""
import sqlalchemy as sa

from alembic import op

revision = "g207credits01"
down_revision = "f206push01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("trial_device_grants",
        sa.Column("device_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("trial_device_exceptions",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("actor_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("reward_tasks",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("max_approvals", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("reward_submissions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("task_id", sa.UUID(), sa.ForeignKey("reward_tasks.id"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("email_hash", sa.String(64), nullable=False),
        sa.Column("device_hash", sa.String(64), nullable=False),
        sa.Column("proof", sa.Text(), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("review_note", sa.String(500)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("task_id", "email_hash", name="uq_reward_task_email"))
    op.create_index("ix_reward_submissions_user_id", "reward_submissions", ["user_id"])
    op.create_table("reward_device_claims",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("task_id", sa.UUID(), sa.ForeignKey("reward_tasks.id"), nullable=False),
        sa.Column("device_hash", sa.String(64), nullable=False),
        sa.Column("submission_id", sa.UUID(), sa.ForeignKey("reward_submissions.id"), nullable=False, unique=True),
        sa.UniqueConstraint("task_id", "device_hash", name="uq_reward_task_device"))


def downgrade():
    for table in ("reward_device_claims", "reward_submissions", "reward_tasks", "trial_device_exceptions", "trial_device_grants"):
        op.drop_table(table)
