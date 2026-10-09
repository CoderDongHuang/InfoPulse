"""Shared API rate limiting."""
from alembic import op
import sqlalchemy as sa

revision = "20261009_0033"
down_revision = "20261009_0032"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("rate_limit_buckets",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.BigInteger(), primary_key=True),
        sa.Column("requests", sa.Integer(), nullable=False))
    op.create_index("ix_rate_limit_buckets_window_start", "rate_limit_buckets", ["window_start"])


def downgrade():
    op.drop_table("rate_limit_buckets")
