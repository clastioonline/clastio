"""Single-use plan licenses with hashed keys."""
from alembic import op
revision = 'd204license01'
down_revision = 'b174cafe0124'
branch_labels = None
depends_on = None

def upgrade():
    op.execute('''CREATE TABLE plan_licenses (
        id UUID PRIMARY KEY, key_hash VARCHAR(64) NOT NULL UNIQUE,
        key_suffix VARCHAR(8) NOT NULL, plan_code VARCHAR(40) NOT NULL REFERENCES plans(code),
        months INTEGER NOT NULL CHECK (months BETWEEN 1 AND 36),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), expires_at TIMESTAMPTZ NOT NULL,
        created_by UUID REFERENCES users(id) ON DELETE SET NULL,
        redeemed_by UUID REFERENCES users(id) ON DELETE SET NULL,
        redeemed_at TIMESTAMPTZ, revoked BOOLEAN NOT NULL DEFAULT false
    )''')

def downgrade():
    op.drop_table('plan_licenses')
