"""Revocable sessions and single-use refresh tokens."""
from alembic import op
import sqlalchemy as sa

revision = "20261009_0031"
down_revision = "20261009_0030"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("auth_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("refresh_jti", sa.String(36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])


def downgrade():
    op.drop_table("auth_sessions")
