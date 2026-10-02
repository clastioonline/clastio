"""Link budget ledger to usage reports for invoice adjustments."""
from alembic import op
import sqlalchemy as sa

revision = "b174cafe0124"
down_revision = "b174cafe0123"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ai_call_reservations", sa.Column("usage_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_ai_call_reservations_usage_id_ai_usage", "ai_call_reservations", "ai_usage",
                          ["usage_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_ai_call_reservations_usage_id", "ai_call_reservations", ["usage_id"])


def downgrade():
    op.drop_column("ai_call_reservations", "usage_id")
