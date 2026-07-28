"""Register the built-in Hacker News source."""

from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_0002"
down_revision: Union[str, None] = "20260728_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SOURCE_ID = "c40dfec7-cac8-4ea7-a568-36d18256740f"


def upgrade() -> None:
    source = sa.table(
        "data_sources",
        sa.column("id", sa.String), sa.column("key", sa.String), sa.column("name", sa.String),
        sa.column("source_type", sa.String), sa.column("base_url", sa.String), sa.column("config", sa.JSON),
        sa.column("enabled", sa.Boolean), sa.column("health_status", sa.String),
        sa.column("sync_interval_minutes", sa.Integer), sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(source, [{
        "id": SOURCE_ID, "key": "hacker-news", "name": "Hacker News", "source_type": "official_api",
        "base_url": "https://hacker-news.firebaseio.com/v0", "config": {"max_items": 30},
        "enabled": True, "health_status": "unknown", "sync_interval_minutes": 30,
        "created_at": now, "updated_at": now,
    }])


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM data_sources WHERE id = :id").bindparams(id=SOURCE_ID))
