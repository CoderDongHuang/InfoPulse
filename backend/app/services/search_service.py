"""Database-backed content search with PostgreSQL full-text support."""

from datetime import datetime

from sqlalchemy import String, and_, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence import ContentItem, DataSource, Event, EventContent


def heat_expression():
    return (
        func.coalesce(ContentItem.like_count, 0)
        + func.coalesce(ContentItem.comment_count, 0) * 2
        + func.coalesce(ContentItem.share_count, 0) * 3
        + func.coalesce(ContentItem.view_count, 0) / 100
    )


async def search_contents(
    db: AsyncSession,
    *,
    q: str = "",
    source_ids: list[str] | None = None,
    types: list[str] | None = None,
    regions: list[str] | None = None,
    languages: list[str] | None = None,
    sentiments: list[str] | None = None,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    heat_min: int | None = None,
    heat_max: int | None = None,
    is_original: bool | None = None,
    is_official: bool | None = None,
    sort: str = "relevance",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    query_text = q.strip()
    dialect = db.get_bind().dialect.name
    heat = heat_expression()
    conditions = [ContentItem.deleted_at.is_(None)]
    rank = literal(0.0)
    if query_text:
        if dialect == "postgresql":
            vector = func.to_tsvector("simple", func.coalesce(ContentItem.title, "") + " " + func.coalesce(ContentItem.body, ""))
            ts_query = func.plainto_tsquery("simple", query_text)
            conditions.append(vector.op("@@")(ts_query))
            rank = func.ts_rank(vector, ts_query)
        else:
            pattern = f"%{query_text}%"
            conditions.append(or_(ContentItem.title.ilike(pattern), ContentItem.body.ilike(pattern)))
            rank = cast(ContentItem.title.ilike(pattern), String)
    if source_ids:
        conditions.append(ContentItem.source_id.in_(source_ids))
    if types:
        conditions.append(ContentItem.content_type.in_(types))
    if regions:
        conditions.append(ContentItem.region.in_(regions))
    if languages:
        conditions.append(ContentItem.language.in_(languages))
    if sentiments:
        conditions.append(ContentItem.sentiment.in_(sentiments))
    if from_at:
        conditions.append(ContentItem.published_at >= from_at)
    if to_at:
        conditions.append(ContentItem.published_at <= to_at)
    if heat_min is not None:
        conditions.append(heat >= heat_min)
    if heat_max is not None:
        conditions.append(heat <= heat_max)
    if is_original is not None:
        conditions.append(ContentItem.is_original.is_(is_original))
    if is_official is not None:
        conditions.append(ContentItem.is_official.is_(is_official))

    filters = and_(*conditions)
    total = int(await db.scalar(select(func.count(ContentItem.id)).where(filters)) or 0)
    event_id = (
        select(Event.id).join(EventContent, EventContent.event_id == Event.id)
        .where(EventContent.content_item_id == ContentItem.id, Event.deleted_at.is_(None)).limit(1).scalar_subquery()
    )
    statement = select(ContentItem, DataSource, event_id.label("event_id"), heat.label("heat"), rank.label("rank")).join(DataSource).where(filters)
    if sort == "heat":
        statement = statement.order_by(heat.desc(), ContentItem.published_at.desc())
    elif sort == "newest" or not query_text:
        statement = statement.order_by(ContentItem.published_at.desc(), ContentItem.fetched_at.desc())
    else:
        statement = statement.order_by(rank.desc(), ContentItem.published_at.desc())
    rows = (await db.execute(statement.offset((page - 1) * page_size).limit(page_size))).all()
    items = []
    for content, source, linked_event_id, heat_value, _rank in rows:
        items.append({
            "id": content.id, "title": content.title, "summary": (content.body or "")[:300],
            "source": {"id": source.id, "key": source.key, "name": source.name}, "author": content.author_name,
            "published_at": content.published_at, "heat": int(heat_value or 0), "sentiment": content.sentiment,
            "tags": content.tags or [], "event": {"id": linked_event_id} if linked_event_id else None,
            "canonical_url": content.canonical_url, "content_type": content.content_type,
            "language": content.language, "region": content.region, "is_original": content.is_original,
            "is_official": content.is_official,
        })
    return {"items": items, "page": page, "page_size": page_size, "total": total, "has_more": page * page_size < total}

