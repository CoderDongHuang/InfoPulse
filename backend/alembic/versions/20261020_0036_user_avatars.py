"""Add bounded, account-owned uploaded avatars."""
from alembic import op
import sqlalchemy as sa

revision = "20261020_0036"
down_revision = "20261018_0035"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("user_avatars",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("image", sa.LargeBinary(), nullable=False))


def downgrade():
    op.drop_table("user_avatars")
