from app.core.routing import APIRouter
from datetime import datetime, timezone
from fastapi import Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.intelligence import Favorite, RecentView, WatchTopic, utc_now
from app.schemas.personalization import TargetRequest, RecentViewRequest, TopicRequest
from app.services.personalization import saved_targets
router = APIRouter(prefix="/api/v1", tags=["Personalization"])
def dump(row):
    return {k: (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).isoformat()
            if isinstance(v, datetime) else v
            for k, v in row.__dict__.items() if not k.startswith("_")}

@router.get("/favorites")
async def list_favorites(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Favorite).where(Favorite.user_id == user.id).order_by(Favorite.created_at.desc()))).all()
    resolved = await saved_targets(db, user.id, rows)
    return [{**dump(row), **item} for row, item in zip(rows, resolved)]
@router.post("/favorites", status_code=201)
async def add_favorite(payload: TargetRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await db.scalar(select(Favorite).where(Favorite.user_id == user.id, Favorite.target_type == payload.target_type, Favorite.target_id == payload.target_id))
    if not row: row = Favorite(user_id=user.id, target_type=payload.target_type, target_id=payload.target_id); db.add(row); await db.flush()
    return dump(row)
@router.delete("/favorites/{target_type}/{target_id}", status_code=204)
async def remove_favorite(target_type: str, target_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Favorite).where(Favorite.user_id == user.id, Favorite.target_type == target_type, Favorite.target_id == target_id))
@router.get("/recent-views")
async def list_views(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(RecentView).where(RecentView.user_id == user.id).order_by(RecentView.viewed_at.desc(), RecentView.id.desc()).limit(30))).all()
    resolved = await saved_targets(db, user.id, rows)
    return [{**dump(row), **item} for row, item in zip(rows, resolved)]
@router.post("/recent-views")
async def record_view(payload: RecentViewRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    target = (await saved_targets(db, user.id, [payload]))[0]
    if not target["available"]:
        raise HTTPException(404, "内容不存在或不可访问")
    query = select(RecentView).where(RecentView.user_id == user.id, RecentView.target_type == payload.target_type, RecentView.target_id == payload.target_id)
    row = await db.scalar(query)
    if row is None:
        try:
            async with db.begin_nested():
                row = RecentView(user_id=user.id, target_type=payload.target_type, target_id=payload.target_id, title=target["title"])
                db.add(row)
                await db.flush()
        except IntegrityError:
            row = await db.scalar(query)
            if row is None:
                raise
    row.title = target["title"]
    row.viewed_at = utc_now()
    await db.commit()
    return {**dump(row), **target}
@router.get("/watch-topics")
async def list_topics(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return [dump(x) for x in (await db.scalars(select(WatchTopic).where(WatchTopic.user_id == user.id).order_by(WatchTopic.created_at.desc()))).all()]
@router.post("/watch-topics", status_code=201)
async def add_topic(payload: TopicRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if await db.scalar(select(WatchTopic.id).where(WatchTopic.user_id == user.id, WatchTopic.name == payload.name)): raise HTTPException(409, "Topic already exists")
    row = WatchTopic(user_id=user.id, **payload.model_dump()); db.add(row); await db.flush(); return dump(row)
@router.delete("/watch-topics/{topic_id}", status_code=204)
async def remove_topic(topic_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(WatchTopic).where(WatchTopic.id == topic_id, WatchTopic.user_id == user.id))
    if not result.rowcount: raise HTTPException(404, "Topic not found")
