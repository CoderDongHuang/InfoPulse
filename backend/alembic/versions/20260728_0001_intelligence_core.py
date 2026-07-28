"""Create legacy-compatible identity tables and intelligence core."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.String(500), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("username"), sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_table(
        "analysis_histories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module", sa.String(20), nullable=False),
        sa.Column("input_params", sa.JSON(), nullable=False),
        sa.Column("output_result", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_analysis_histories_user_id", "analysis_histories", ["user_id"])
    op.create_table(
        "data_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(60), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("base_url", sa.String(1000), nullable=False, server_default=""),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("health_status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("sync_interval_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_data_sources_key", "data_sources", ["key"])
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("fetched_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("cursor", sa.JSON(), nullable=False),
        sa.Column("error_summary", sa.Text()),
        sa.Column("diagnostic_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sync_runs_source_id", "sync_runs", ["source_id"])
    op.create_index("ix_sync_runs_status", "sync_runs", ["status"])
    op.create_table(
        "content_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("external_id", sa.String(500), nullable=False),
        sa.Column("canonical_url", sa.String(2000), nullable=False),
        sa.Column("title", sa.Text(), nullable=False), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author_name", sa.String(300), nullable=False),
        sa.Column("author_external_id", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(30), nullable=False),
        sa.Column("language", sa.String(16), nullable=False), sa.Column("region", sa.String(80), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)), sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("view_count", sa.BigInteger()), sa.Column("comment_count", sa.BigInteger()),
        sa.Column("like_count", sa.BigInteger()), sa.Column("share_count", sa.BigInteger()),
        sa.Column("is_official", sa.Boolean(), nullable=False), sa.Column("is_original", sa.Boolean()),
        sa.Column("content_hash", sa.String(64), nullable=False), sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("source_id", "external_id", name="uq_content_source_external"),
    )
    for name, columns in (("source_id", ["source_id"]), ("content_type", ["content_type"]), ("language", ["language"]), ("published_at", ["published_at"]), ("content_hash", ["content_hash"])):
        op.create_index(f"ix_content_items_{name}", "content_items", columns)
    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("title", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(600), nullable=False, unique=True), sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("category", sa.String(80), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("heat_score", sa.Float(), nullable=False), sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)), sa.Column("last_activity_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    for name in ("slug", "category", "status", "heat_score", "risk_score", "last_activity_at"):
        op.create_index(f"ix_events_{name}", "events", [name])
    op.create_table(
        "event_contents",
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("content_item_id", sa.String(36), sa.ForeignKey("content_items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("relevance_score", sa.Float(), nullable=False), sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("added_by", sa.String(20), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for table in ("event_contents", "events", "content_items", "sync_runs", "data_sources", "analysis_histories", "users"):
        op.drop_table(table)
