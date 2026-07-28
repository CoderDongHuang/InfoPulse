"""Add administrator boundary and production query indexes."""
from alembic import op
import sqlalchemy as sa

revision = "20260729_0013"
down_revision = "20260729_0012"
branch_labels = None
depends_on = None

INDEXES = [
    ("ix_content_source_published_active", "content_items", ["source_id", "published_at", "deleted_at"]),
    ("ix_events_status_activity_active", "events", ["status", "last_activity_at", "deleted_at"]),
    ("ix_events_risk_activity", "events", ["risk_score", "last_activity_at"]),
    ("ix_task_runs_status_retry", "task_runs", ["status", "retry_at"]),
    ("ix_notifications_user_status_created", "notifications", ["user_id", "status", "created_at"]),
    ("ix_alert_incidents_user_status_triggered", "alert_incidents", ["user_id", "status", "triggered_at"]),
    ("ix_knowledge_chunks_owner_base", "knowledge_chunks", ["user_id", "knowledge_base_id", "document_id"]),
    ("ix_audit_logs_target_created", "audit_logs", ["target_type", "target_id", "created_at"]),
]

def upgrade():
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)

def downgrade():
    for name, table, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table)
    op.drop_column("users", "is_admin")
