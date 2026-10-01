"""rename the assistant plan to Genie Assistant (the product is now Clastio)

Revision ID: 3c1e7a9d2b10
Revises: 29b0142b86ed
"""
from typing import Sequence, Union

from alembic import op

revision: str = "3c1e7a9d2b10"
down_revision: Union[str, None] = "29b0142b86ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Only the untouched default name: a name an admin chose is kept.
    op.execute("UPDATE plans SET name = 'Genie Assistant' WHERE code = 'assistant' AND name = 'AI Teaching Assistant'")


def downgrade() -> None:
    op.execute("UPDATE plans SET name = 'AI Teaching Assistant' WHERE code = 'assistant' AND name = 'Genie Assistant'")
