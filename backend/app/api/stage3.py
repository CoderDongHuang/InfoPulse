from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.intelligence import ChannelFollow, RecommendationFeedback
from app.schemas.personalization import FeedbackRequest
from app.services.stage3 import CHANNELS, dashboard_data, discover_data, workspace_data
router = APIRouter(prefix="/api/v1", tags=["Dashboard and Discover"])

@router.get("/dashboard")
async def dashboard(days: int = Query(7, ge=1, le=90), _user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)): return await dashboard_data(db, days)
@router.get("/dashboard/trends")
async def trends(days: int = Query(30, ge=1, le=90), _user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)): return (await dashboard_data(db, days))["trends"]
@router.get("/discover/channels")
async def channels(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    followed = set((await db.scalars(select(ChannelFollow.channel_id).where(ChannelFollow.user_id == user.id))).all())
    return [{"id": key, "name": value[0], "followed": key in followed} for key, value in CHANNELS.items()]
@router.post("/discover/channels/{channel_id}/follow", status_code=201)
async def follow(channel_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if channel_id not in CHANNELS: raise HTTPException(404, "Channel not found")
    row = await db.scalar(select(ChannelFollow).where(ChannelFollow.user_id == user.id, ChannelFollow.channel_id == channel_id))
    if not row: row = ChannelFollow(user_id=user.id, channel_id=channel_id); db.add(row); await db.flush()
    return {"channel_id": channel_id, "followed": True}
@router.delete("/discover/channels/{channel_id}/follow", status_code=204)
async def unfollow(channel_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)): await db.execute(delete(ChannelFollow).where(ChannelFollow.user_id == user.id, ChannelFollow.channel_id == channel_id))
@router.get("/discover")
async def discover(channel: str="ai", range: Literal["day","week","month"]="day", page: int=Query(1,ge=1), page_size: int=Query(20,ge=1,le=100), user: User=Depends(get_current_user), db: AsyncSession=Depends(get_db)):
    if channel not in CHANNELS: raise HTTPException(404, "Channel not found")
    return await discover_data(db, user.id, channel, range, page, page_size)
@router.post("/discover/items/{item_id}/feedback")
async def feedback(item_id: str, payload: FeedbackRequest, user: User=Depends(get_current_user), db: AsyncSession=Depends(get_db)):
    row = await db.scalar(select(RecommendationFeedback).where(RecommendationFeedback.user_id == user.id, RecommendationFeedback.target_type == "content", RecommendationFeedback.target_id == item_id))
    if row: row.feedback_type=payload.feedback_type; row.reason=payload.reason
    else: row=RecommendationFeedback(user_id=user.id,target_type="content",target_id=item_id,**payload.model_dump()); db.add(row)
    await db.flush(); return {"item_id": item_id, "feedback_type": row.feedback_type, "ranking_effect": "hidden" if row.feedback_type in {"not_interested","irrelevant"} else "downranked"}
@router.get("/workspace")
async def workspace(user: User=Depends(get_current_user), db: AsyncSession=Depends(get_db)): return await workspace_data(db, user.id)
