"""Management endpoints for real external data sources."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.intelligence import DataSource, SyncRun
from app.models.user import User
from app.schemas.sources import DataSourceResponse, SyncRunResponse
from app.services.source_sync import ensure_builtin_sources, sync_source

router = APIRouter(prefix="/api/v1/sources", tags=["Data Sources"])


async def _get_source(db: AsyncSession, source_id: str) -> DataSource:
    source = await db.get(DataSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return source


@router.get("", response_model=list[DataSourceResponse])
async def list_sources(
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_builtin_sources(db)
    rows = await db.scalars(select(DataSource).order_by(DataSource.name))
    return list(rows.all())


@router.post("/{source_id}/sync", response_model=SyncRunResponse)
async def trigger_sync(
    source_id: str,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_builtin_sources(db)
    source = await _get_source(db, source_id)
    return await sync_source(db, source)


@router.get("/{source_id}/sync-runs", response_model=list[SyncRunResponse])
async def list_sync_runs(
    source_id: str,
    limit: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_source(db, source_id)
    rows = await db.scalars(
        select(SyncRun).where(SyncRun.source_id == source_id).order_by(SyncRun.created_at.desc()).limit(limit)
    )
    return list(rows.all())

