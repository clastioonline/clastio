"""Durable subscription checkout reservations and bounded Clerk account checks."""
from alembic import op
import sqlalchemy as sa

revision = "e205checkout01"
down_revision = "d204license01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("clerk_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table("subscription_checkouts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("plan_code", sa.String(40), sa.ForeignKey("plans.code"), nullable=False),
        sa.Column("interval", sa.String(10), nullable=False),
        sa.Column("coupon_code", sa.String(100)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider_session_id", sa.String(255)),
        sa.Column("checkout_url", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider", "provider_session_id"),
    )
    op.create_index("ix_subscription_checkouts_pending_user", "subscription_checkouts", ["user_id"],
                    unique=True, postgresql_where=sa.text("status IN ('creating', 'open', 'processing')"))


def downgrade():
    op.drop_table("subscription_checkouts")
    op.drop_column("users", "clerk_checked_at")
