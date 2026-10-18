"""Add encrypted, account-owned service settings."""
from alembic import op
import sqlalchemy as sa

revision = "20261018_0035"
down_revision = "20261014_0034"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("user_service_settings",
                    sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
                    sa.Column("ciphertext", sa.Text(), nullable=False),
                    sa.Column("revision", sa.Integer(), nullable=False))


def downgrade():
    op.drop_table("user_service_settings")
