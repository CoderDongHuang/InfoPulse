"""Normalized content detail API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.intelligence import ContentItem, DataSource, Event, EventContent
from app.models.user import User

router = APIRouter(prefix="/api/v1/contents", tags=["Contents"])


@router.get("/{content_id}")
async def content_detail(content_id: str, _user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(ContentItem, DataSource).join(DataSource).where(ContentItem.id == content_id, ContentItem.deleted_at.is_(None)))).first()
    if not row: raise HTTPException(status_code=404, detail="内容不存在")
    content, source = row
    events = (await db.execute(select(Event.id, Event.title).join(EventContent).where(EventContent.content_item_id == content.id, Event.deleted_at.is_(None)))).all()
    return {
        "id": content.id, "title": content.title, "body": content.body, "canonical_url": content.canonical_url,
        "source": {"id": source.id, "key": source.key, "name": source.name, "base_url": source.base_url},
        "author": {"name": content.author_name, "external_id": content.author_external_id},
        "content_type": content.content_type, "language": content.language, "region": content.region,
        "published_at": content.published_at, "fetched_at": content.fetched_at, "sentiment": content.sentiment,
        "tags": content.tags, "entities": content.entities, "metrics": {"views": content.view_count, "comments": content.comment_count, "likes": content.like_count, "shares": content.share_count},
        "is_original": content.is_original, "is_official": content.is_official,
        "events": [{"id": event_id, "title": title} for event_id, title in events], "raw_payload": content.raw_payload,
    }
