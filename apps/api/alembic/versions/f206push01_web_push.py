"""Per-device Web Push consent and durable delivery outbox."""

from alembic import op
import sqlalchemy as sa

revision = "f206push01"
down_revision = "e205checkout01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("push_subscriptions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.UUID(), sa.ForeignKey("user_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(100), nullable=False),
        sa.Column("auth", sa.String(30), nullable=False),
        sa.Column("device_name", sa.String(80), nullable=False),
        sa.Column("marketing_enabled", sa.Boolean(), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])
    op.create_table("push_deliveries",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("subscription_id", sa.UUID(), sa.ForeignKey("push_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("link", sa.String(500), nullable=False),
        sa.Column("dedupe_key", sa.String(300), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("send_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(200)),
        sa.UniqueConstraint("subscription_id", "dedupe_key"),
    )
    op.create_index("ix_push_deliveries_status", "push_deliveries", ["status"])
    op.create_index("ix_push_deliveries_send_after", "push_deliveries", ["send_after"])


def downgrade():
    op.drop_table("push_deliveries")
    op.drop_table("push_subscriptions")
