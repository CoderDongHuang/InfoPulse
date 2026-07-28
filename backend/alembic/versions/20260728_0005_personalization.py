"""Add Stage 3 personalization records."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
revision: str = "20260728_0005"
down_revision: Union[str, None] = "20260728_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    def base(): return [sa.Column("id", sa.String(36), primary_key=True), sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)]
    op.create_table("favorites", *base(), sa.Column("target_type", sa.String(20), nullable=False), sa.Column("target_id", sa.String(36), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("user_id", "target_type", "target_id", name="uq_favorite_target"))
    op.create_table("recent_views", *base(), sa.Column("target_type", sa.String(20), nullable=False), sa.Column("target_id", sa.String(36), nullable=False), sa.Column("title", sa.String(500), nullable=False), sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("user_id", "target_type", "target_id", name="uq_recent_view_target"))
    op.create_table("watch_topics", *base(), sa.Column("name", sa.String(120), nullable=False), sa.Column("keywords", sa.JSON(), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("user_id", "name", name="uq_watch_topic_name"))
    op.create_table("channel_follows", *base(), sa.Column("channel_id", sa.String(60), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("user_id", "channel_id", name="uq_channel_follow"))
    op.create_table("recommendation_feedback", *base(), sa.Column("target_type", sa.String(20), nullable=False), sa.Column("target_id", sa.String(36), nullable=False), sa.Column("feedback_type", sa.String(30), nullable=False), sa.Column("reason", sa.String(500), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("user_id", "target_type", "target_id", name="uq_recommendation_feedback"))
    for table in ("favorites", "recent_views", "watch_topics", "channel_follows", "recommendation_feedback"): op.create_index(f"ix_{table}_user_id", table, ["user_id"])
    op.create_index("ix_favorites_target_id", "favorites", ["target_id"])
    op.create_index("ix_recent_views_target_id", "recent_views", ["target_id"]); op.create_index("ix_recent_views_viewed_at", "recent_views", ["viewed_at"])
    op.create_index("ix_recommendation_feedback_target_id", "recommendation_feedback", ["target_id"])

def downgrade() -> None:
    for table in ("recommendation_feedback", "channel_follows", "watch_topics", "recent_views", "favorites"): op.drop_table(table)
