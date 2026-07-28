"""Event timeline workflow."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.analysis_history import AnalysisHistory
from app.models.user import User
from app.schemas.workflows import TimelineRequest
from app.services.workflows import build_timeline, collect_posts

router = APIRouter(prefix="/api/v1/timeline", tags=["Event Timeline"])


@router.post("/build")
async def build(payload: TimelineRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    posts, sources = await collect_posts(payload.topic, payload.platforms, payload.max_items)
    if not posts:
        raise HTTPException(status_code=422, detail="没有找到可用于梳理的公开信息")
    result = await build_timeline(payload.topic, posts, sources)
    history = AnalysisHistory(
        user_id=current_user.id,
        module="timeline",
        input_params=payload.model_dump(),
        output_result=result,
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    db.add(history)
    await db.commit()
    return result
