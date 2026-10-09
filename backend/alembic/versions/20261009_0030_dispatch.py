"""Durable approved connector outbox."""
from alembic import op
import sqlalchemy as sa

revision = "20261009_0030"
down_revision = "20260804_0029"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("dispatch_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(36)),
        sa.Column("installation_id", sa.String(36), sa.ForeignKey("connector_installations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action_id", sa.String(36)),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_dispatch_key"))
    op.create_index("ix_dispatch_jobs_organization_id", "dispatch_jobs", ["organization_id"])
    op.create_index("ix_dispatch_jobs_status", "dispatch_jobs", ["status"])
    with op.batch_alter_table("knowledge_documents") as batch:
        batch.add_column(sa.Column("processing_attempts", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("lease_until", sa.DateTime(timezone=True)))
        batch.create_index("ix_knowledge_documents_lease_until", ["lease_until"])


def downgrade():
    with op.batch_alter_table("knowledge_documents") as batch:
        batch.drop_index("ix_knowledge_documents_lease_until")
        batch.drop_column("lease_until")
        batch.drop_column("processing_attempts")
    op.drop_table("dispatch_jobs")
