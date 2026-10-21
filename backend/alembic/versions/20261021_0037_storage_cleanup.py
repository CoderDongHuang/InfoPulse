"""Durable account storage cleanup outbox."""
from alembic import op
import sqlalchemy as sa

revision = "20261021_0037"
down_revision = "20261020_0036"
branch_labels = depends_on = None


def upgrade():
    op.create_table("storage_cleanup",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("backend", sa.String(20), nullable=False),
        sa.Column("storage_key", sa.String(1000), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("storage_cleanup")
