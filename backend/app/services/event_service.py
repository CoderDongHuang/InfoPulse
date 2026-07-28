"""Manual event lifecycle operations with immutable audit records."""

import hashlib
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.intelligence import AuditLog, ContentItem, DataSource, Event, EventContent, EventEntity
from app.services.event_clustering import event_scores, normalized_entities


def snapshot(event: Event) -> dict:
    return {key: (value.isoformat() if isinstance(value, datetime) else value) for key, value in {
        "title": event.title, "category": event.category, "status": event.status, "summary": event.summary,
        "heat_score": event.heat_score, "risk_score": event.risk_score, "confidence": event.confidence,
        "started_at": event.started_at, "ended_at": event.ended_at, "last_activity_at": event.last_activity_at,
        "manual_locked": event.manual_locked, "risk_notes": event.risk_notes,
    }.items()}


async def audit(db: AsyncSession, user_id: str, action: str, event: Event, before: dict, after: dict) -> None:
    db.add(AuditLog(user_id=user_id, action=action, target_type="event", target_id=event.id, before_data=before, after_data=after))


async def get_event_or_error(db: AsyncSession, event_id: str) -> Event:
    event = await db.scalar(select(Event).where(Event.id == event_id, Event.deleted_at.is_(None)))
    if not event: raise AppError("EVENT_NOT_FOUND", "事件不存在", 404)
    return event


async def create_manual_event(db: AsyncSession, user_id: str, title: str, category: str, content_ids: list[str]) -> Event:
    unique_ids = list(dict.fromkeys(content_ids))
    contents = list((await db.scalars(select(ContentItem).where(ContentItem.id.in_(unique_ids), ContentItem.deleted_at.is_(None)))).all())
    if len(contents) != len(unique_ids): raise AppError("CONTENT_NOT_FOUND", "部分内容不存在", 404)
    digest = hashlib.sha1(f"{title}|{'|'.join(sorted(unique_ids))}|{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()[:12]
    event = Event(title=title, slug=f"manual-{digest}", summary=(contents[0].body or contents[0].title)[:600], category=category,
        status="detected", created_by=user_id, manual_locked=True)
    db.add(event); await db.flush()
    for index, content in enumerate(contents):
        db.add(EventContent(event_id=event.id, content_item_id=content.id, relevance_score=1.0,
            is_primary=index == 0, added_by="user"))
    await _refresh_metrics(db, event, contents)
    await audit(db, user_id, "event.create", event, {}, snapshot(event)); await db.flush(); return event


async def update_manual_event(db: AsyncSession, user_id: str, event: Event, changes: dict) -> Event:
    before = snapshot(event)
    for field, value in changes.items(): setattr(event, field, value)
    event.manual_locked = True; event.updated_at = datetime.now(timezone.utc)
    await audit(db, user_id, "event.update", event, before, snapshot(event)); await db.flush(); return event


async def merge_events(db: AsyncSession, user_id: str, target: Event, source_ids: list[str], keep_title: str | None) -> Event:
    sources = list((await db.scalars(select(Event).where(Event.id.in_(source_ids), Event.deleted_at.is_(None)))).all())
    if len(sources) != len(source_ids): raise AppError("EVENT_NOT_FOUND", "部分待合并事件不存在", 404)
    before = snapshot(target)
    target_content_ids = set((await db.scalars(select(EventContent.content_item_id).where(EventContent.event_id == target.id))).all())
    source_links = (await db.scalars(select(EventContent).where(EventContent.event_id.in_(source_ids)))).all()
    for link in source_links:
        if link.content_item_id not in target_content_ids:
            db.add(EventContent(event_id=target.id, content_item_id=link.content_item_id, relevance_score=link.relevance_score,
                is_primary=False, added_by="user")); target_content_ids.add(link.content_item_id)
    for source in sources:
        source.deleted_at = datetime.now(timezone.utc); source.status = "closed"; source.manual_locked = True
    if keep_title: target.title = keep_title
    target.manual_locked = True; target.updated_at = datetime.now(timezone.utc)
    await db.flush()
    contents = list((await db.scalars(select(ContentItem).where(ContentItem.id.in_(target_content_ids)))).all())
    await _refresh_metrics(db, target, contents)
    await audit(db, user_id, "event.merge", target, before, {**snapshot(target), "merged_event_ids": source_ids})
    await db.flush(); return target


async def _refresh_metrics(db: AsyncSession, event: Event, contents: list[ContentItem]) -> None:
    source_count = int(await db.scalar(select(func.count(func.distinct(ContentItem.source_id))).where(ContentItem.id.in_([item.id for item in contents]))) or 0)
    event.heat_score, event.risk_score, event.confidence = event_scores(contents, source_count)
    event.started_at = min((item.published_at for item in contents if item.published_at), default=event.started_at)
    event.last_activity_at = max((item.published_at for item in contents if item.published_at), default=event.last_activity_at)
    await db.execute(delete(EventEntity).where(EventEntity.event_id == event.id))
    counts = Counter(entity for content in contents for entity in normalized_entities(content))
    for name, count in counts.most_common(20): db.add(EventEntity(event_id=event.id, name=name[:300], entity_type="keyword", mention_count=count))
