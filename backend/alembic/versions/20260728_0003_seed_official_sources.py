"""Register GitHub, DEV Community, and arXiv sources."""

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_0003"
down_revision: Union[str, None] = "20260728_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SOURCES = [
    {"id": "0bad6397-d086-466f-a549-4c2ae0b49a37", "key": "github", "name": "GitHub", "base_url": "https://api.github.com", "interval": 30},
    {"id": "69ba6d40-44fe-4dfb-85f9-7e0acfecd63d", "key": "devto", "name": "DEV Community", "base_url": "https://dev.to/api", "interval": 60},
    {"id": "32dfa439-0178-44e9-976f-68082b9868e5", "key": "arxiv", "name": "arXiv", "base_url": "https://export.arxiv.org/api", "interval": 120},
]


def upgrade() -> None:
    source = sa.table(
        "data_sources", sa.column("id", sa.String), sa.column("key", sa.String), sa.column("name", sa.String),
        sa.column("source_type", sa.String), sa.column("base_url", sa.String), sa.column("config", sa.JSON),
        sa.column("enabled", sa.Boolean), sa.column("health_status", sa.String),
        sa.column("sync_interval_minutes", sa.Integer), sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(source, [{
        "id": item["id"], "key": item["key"], "name": item["name"], "source_type": "official_api",
        "base_url": item["base_url"], "config": {"max_items": 30}, "enabled": True,
        "health_status": "unknown", "sync_interval_minutes": item["interval"], "created_at": now, "updated_at": now,
    } for item in SOURCES])


def downgrade() -> None:
    ids = ",".join(f"'{item['id']}'" for item in SOURCES)
    op.execute(sa.text(f"DELETE FROM data_sources WHERE id IN ({ids})"))
