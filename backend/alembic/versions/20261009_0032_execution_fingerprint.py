"""Bind delivery idempotency to the complete approved request."""
from alembic import op
import sqlalchemy as sa

revision = "20261009_0032"
down_revision = "20261009_0031"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("connector_executions") as batch:
        batch.add_column(sa.Column("request_hash", sa.String(64), nullable=False, server_default=""))


def downgrade():
    with op.batch_alter_table("connector_executions") as batch:
        batch.drop_column("request_hash")
