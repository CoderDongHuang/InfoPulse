"""Event detection and research APIs."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.intelligence import AuditLog, ContentItem, DataSource, Event, EventContent, EventEntity
from app.schemas.events import ClusterRequest, ClusterResponse, EventCreateRequest, EventMergeRequest, EventUpdateRequest
from app.services.event_clustering import cluster_recent_content
from app.services.event_service import create_manual_event, get_event_or_error, merge_events, update_manual_event

router = APIRouter(prefix="/api/v1/events", tags=["Events"])


@router.post("/cluster", response_model=ClusterResponse)
async def cluster_events(payload: ClusterRequest, _user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await cluster_recent_content(db, hours=payload.hours, threshold=payload.threshold)


@router.post("/merge")
async def merge(payload: EventMergeRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    target = await get_event_or_error(db, payload.target_event_id)
    return _event_dict(await merge_events(db, user.id, target, payload.source_event_ids, payload.keep_title), 0, 0)


@router.get("")
async def list_events(
    tab: Literal["hot", "latest", "risk", "rising", "responded", "closed"] = "latest",
    statuses: list[str] | None = Query(None, alias="status[]"), categories: list[str] | None = Query(None, alias="category[]"),
    risk_min: float | None = Query(None, ge=0, le=100), heat_min: float | None = Query(None, ge=0, le=100),
    from_at: datetime | None = Query(None, alias="from"), to_at: datetime | None = Query(None, alias="to"),
    sort: Literal["heat", "risk", "latest"] = "latest", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    _user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    conditions = [Event.deleted_at.is_(None)]
    if statuses: conditions.append(Event.status.in_(statuses))
    if categories: conditions.append(Event.category.in_(categories))
    if risk_min is not None: conditions.append(Event.risk_score >= risk_min)
    if heat_min is not None: conditions.append(Event.heat_score >= heat_min)
    if from_at: conditions.append(Event.last_activity_at >= from_at)
    if to_at: conditions.append(Event.last_activity_at <= to_at)
    if tab in {"rising", "responded", "closed"}: conditions.append(Event.status == tab)
    if tab == "risk": conditions.append(Event.risk_score >= max(risk_min or 0, 40))
    count = int(await db.scalar(select(func.count(Event.id)).where(*conditions)) or 0)
    statement = select(Event).where(*conditions)
    order = Event.heat_score.desc() if sort == "heat" or tab == "hot" else Event.risk_score.desc() if sort == "risk" or tab == "risk" else Event.last_activity_at.desc()
    events = list((await db.scalars(statement.order_by(order).offset((page - 1) * page_size).limit(page_size))).all())
    items = []
    for event in events:
        content_count, source_count = await _counts(db, event.id)
        items.append(_event_dict(event, content_count, source_count))
    return {"items": items, "page": page, "page_size": page_size, "total": count, "has_more": page * page_size < count}


@router.post("")
async def create_event(payload: EventCreateRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    event = await create_manual_event(db, user.id, payload.title, payload.category, payload.content_ids)
    content_count, source_count = await _counts(db, event.id); return _event_dict(event, content_count, source_count)


@router.get("/{event_id}")
async def event_detail(event_id: str, _user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    event = await get_event_or_error(db, event_id); content_count, source_count = await _counts(db, event.id)
    entities = (await db.scalars(select(EventEntity).where(EventEntity.event_id == event.id).order_by(EventEntity.mention_count.desc()))).all()
    return {**_event_dict(event, content_count, source_count), "entities": [{"name": item.name, "type": item.entity_type, "mention_count": item.mention_count} for item in entities], "risk_notes": event.risk_notes, "permissions": {"can_edit": True, "can_merge": True}}


@router.patch("/{event_id}")
async def update_event(event_id: str, payload: EventUpdateRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    event = await update_manual_event(db, user.id, await get_event_or_error(db, event_id), payload.model_dump(exclude_none=True))
    content_count, source_count = await _counts(db, event.id); return _event_dict(event, content_count, source_count)


@router.get("/{event_id}/timeline")
async def event_timeline(event_id: str, _user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await get_event_or_error(db, event_id)
    rows = (await db.execute(select(ContentItem, DataSource, EventContent).join(EventContent, EventContent.content_item_id == ContentItem.id).join(DataSource).where(EventContent.event_id == event_id).order_by(ContentItem.published_at))).all()
    return {"items": [{"content_id": content.id, "time": content.published_at, "title": content.title, "summary": content.body[:240], "source": source.name, "url": content.canonical_url, "relevance": link.relevance_score, "is_primary": link.is_primary} for content, source, link in rows]}


@router.get("/{event_id}/sources")
async def event_sources(event_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), _user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await get_event_or_error(db, event_id)
    base = select(ContentItem, DataSource, EventContent).join(EventContent, EventContent.content_item_id == ContentItem.id).join(DataSource).where(EventContent.event_id == event_id)
    total = int(await db.scalar(select(func.count(EventContent.content_item_id)).where(EventContent.event_id == event_id)) or 0)
    rows = (await db.execute(base.order_by(ContentItem.published_at.desc()).offset((page - 1) * page_size).limit(page_size))).all()
    return {"items": [{"id": content.id, "title": content.title, "source": source.name, "published_at": content.published_at, "url": content.canonical_url, "relevance": link.relevance_score, "is_primary": link.is_primary} for content, source, link in rows], "page": page, "page_size": page_size, "total": total, "has_more": page * page_size < total}


@router.get("/{event_id}/audit-logs")
async def event_audit_logs(event_id: str, _user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await get_event_or_error(db, event_id)
    rows = (await db.scalars(select(AuditLog).where(AuditLog.target_type == "event", AuditLog.target_id == event_id).order_by(AuditLog.created_at.desc()))).all()
    return [{"id": row.id, "user_id": row.user_id, "action": row.action, "before": row.before_data, "after": row.after_data, "created_at": row.created_at} for row in rows]


async def _counts(db: AsyncSession, event_id: str) -> tuple[int, int]:
    content_count = int(await db.scalar(select(func.count(EventContent.content_item_id)).where(EventContent.event_id == event_id)) or 0)
    source_count = int(await db.scalar(select(func.count(func.distinct(ContentItem.source_id))).join(EventContent, EventContent.content_item_id == ContentItem.id).where(EventContent.event_id == event_id)) or 0)
    return content_count, source_count


def _event_dict(event: Event, content_count: int, source_count: int) -> dict:
    return {"id": event.id, "title": event.title, "summary": event.summary, "category": event.category, "status": event.status,
        "heat_score": event.heat_score, "risk_score": event.risk_score, "confidence": event.confidence,
        "started_at": event.started_at, "ended_at": event.ended_at, "last_activity_at": event.last_activity_at,
        "updated_at": event.updated_at, "content_count": content_count, "source_count": source_count, "manual_locked": event.manual_locked}
