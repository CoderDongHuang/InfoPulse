"""Event detection and research APIs."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.events import ClusterRequest, ClusterResponse
from app.services.event_clustering import cluster_recent_content

router = APIRouter(prefix="/api/v1/events", tags=["Events"])


@router.post("/cluster", response_model=ClusterResponse)
async def cluster_events(payload: ClusterRequest, _user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await cluster_recent_content(db, hours=payload.hours, threshold=payload.threshold)

