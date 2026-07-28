"""Add search metadata, saved searches, event entities, and audit logs."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_0004"
down_revision: Union[str, None] = "20260728_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("content_items", sa.Column("sentiment", sa.String(20), nullable=False, server_default="unknown"))
    op.add_column("content_items", sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("content_items", sa.Column("entities", sa.JSON(), nullable=False, server_default="[]"))
    op.create_index("ix_content_items_sentiment", "content_items", ["sentiment"])
    op.add_column("events", sa.Column("manual_locked", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("events", sa.Column("risk_notes", sa.Text(), nullable=False, server_default=""))

    op.create_table(
        "saved_searches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("query", sa.String(500), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_saved_searches_user_id", "saved_searches", ["user_id"])
    op.create_table(
        "event_entities", sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False), sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("mention_count", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", "name", name="uq_event_entity_name"),
    )
    op.create_index("ix_event_entities_event_id", "event_entities", ["event_id"])
    op.create_index("ix_event_entities_name", "event_entities", ["name"])
    op.create_table(
        "audit_logs", sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(80), nullable=False), sa.Column("target_type", sa.String(40), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False), sa.Column("before_data", sa.JSON(), nullable=False),
        sa.Column("after_data", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name in ("user_id", "action", "target_type", "target_id", "created_at"):
        op.create_index(f"ix_audit_logs_{name}", "audit_logs", [name])

    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE INDEX ix_content_items_search ON content_items USING GIN (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(body, '')))")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_content_items_search")
    for table in ("audit_logs", "event_entities", "saved_searches"):
        op.drop_table(table)
    op.drop_column("events", "risk_notes")
    op.drop_column("events", "manual_locked")
    op.drop_index("ix_content_items_sentiment", table_name="content_items")
    op.drop_column("content_items", "entities")
    op.drop_column("content_items", "tags")
    op.drop_column("content_items", "sentiment")
