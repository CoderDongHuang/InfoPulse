"""Rank normalized, persisted content without depending on a single platform."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence import ContentItem, DataSource

CATEGORY_LABELS = {"repository": "开源项目", "paper": "研究论文", "article": "行业资讯"}


async def fetch_intelligence_ranking(db: AsyncSession, limit: int = 30) -> dict:
    rows = (await db.execute(
        select(ContentItem, DataSource)
        .join(DataSource, DataSource.id == ContentItem.source_id)
        .where(ContentItem.deleted_at.is_(None), DataSource.enabled.is_(True))
        .order_by(ContentItem.published_at.desc(), ContentItem.fetched_at.desc())
        .limit(200)
    )).all()

    now = datetime.now(timezone.utc)
    ranked = []
    for content, source in rows:
        engagement = (
            int(content.like_count or 0)
            + int(content.comment_count or 0) * 2
            + int(content.share_count or 0) * 3
        )
        published = content.published_at
        if published and published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        age_hours = max(0, (now - published).total_seconds() / 3600) if published else 168
        heat = max(1, engagement + round(max(0, 168 - age_hours)))
        ranked.append({
            "platform": source.name,
            "title": content.title,
            "heat": heat,
            "url": content.canonical_url,
            "category": CATEGORY_LABELS.get(content.content_type, content.content_type),
            "label": "NEW" if age_hours <= 24 else "",
            "published_at": content.published_at,
            "source_key": source.key,
        })
    ranked.sort(key=lambda item: item["heat"], reverse=True)
    items = [{"rank": index + 1, **item} for index, item in enumerate(ranked[:limit])]
    return {
        "items": items,
        "source": "统一情报数据中心",
        "source_url": "/sources",
        "status": "live" if items else "unavailable",
        "message": "来自已同步官方 API 与 RSS 的真实内容" if items else "尚无已同步内容，请先到数据源中心执行同步",
        "updated_at": now.astimezone().isoformat(timespec="seconds"),
    }
