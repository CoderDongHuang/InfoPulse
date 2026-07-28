"""Management endpoints for real external data sources."""

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.intelligence import ContentItem, DataSource, SyncRun
from app.models.user import User
from app.schemas.sources import (
    ConnectionTestResponse, DataSourceResponse, RssSourceRequest, RssValidateRequest,
    SourceUpdateRequest, SyncRunResponse,
)
from app.services.collectors.rss import RssCollector, validate_public_feed_url
from app.services.source_sync import ensure_builtin_sources, sync_source, test_source_connection

router = APIRouter(prefix="/api/v1/sources", tags=["Data Sources"])


def _now():
    return datetime.now(timezone.utc)


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


@router.post("/rss/validate", response_model=ConnectionTestResponse)
async def validate_rss(
    payload: RssValidateRequest,
    _current_user: User = Depends(get_current_user),
):
    try:
        items = await RssCollector(str(payload.feed_url)).collect(1)
        return ConnectionTestResponse(status="healthy", item_count=len(items), message="RSS 连接成功", checked_at=_now())
    except Exception as exc:
        return ConnectionTestResponse(status="error", message=str(exc)[:500], checked_at=_now())


@router.post("/rss", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def add_rss_source(
    payload: RssSourceRequest,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    feed_url = str(payload.feed_url)
    validate_public_feed_url(feed_url)
    duplicate = await db.scalar(select(DataSource).where(DataSource.base_url == feed_url, DataSource.source_type == "rss"))
    if duplicate:
        raise HTTPException(status_code=409, detail="该 RSS 已经存在")
    key_base = re.sub(r"[^a-z0-9]+", "-", payload.name.lower()).strip("-") or "feed"
    source = DataSource(
        key=f"rss-{key_base}-{uuid.uuid4().hex[:8]}", name=payload.name.strip(), source_type="rss",
        base_url=feed_url, config={"feed_url": feed_url, "max_items": 30},
        sync_interval_minutes=payload.sync_interval_minutes,
    )
    db.add(source)
    await db.flush()
    return source


@router.get("/{source_id}", response_model=DataSourceResponse)
async def get_source_detail(
    source_id: str,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_source(db, source_id)


@router.patch("/{source_id}", response_model=DataSourceResponse)
async def update_source(
    source_id: str,
    payload: SourceUpdateRequest,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = await _get_source(db, source_id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(source, field, value)
    source.updated_at = _now()
    await db.flush()
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: str,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = await _get_source(db, source_id)
    if source.source_type != "rss":
        raise HTTPException(status_code=409, detail="内置数据源不能删除")
    content_count = await db.scalar(select(func.count(ContentItem.id)).where(ContentItem.source_id == source.id))
    if content_count:
        raise HTTPException(status_code=409, detail="该 RSS 已有同步内容，请先停用而不是删除")
    await db.delete(source)


@router.post("/{source_id}/test", response_model=ConnectionTestResponse)
async def test_connection(
    source_id: str,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = await _get_source(db, source_id)
    try:
        count = await test_source_connection(source)
        source.health_status = "healthy"
        source.last_error = None
        message = "连接成功"
    except Exception as exc:
        count = 0
        source.health_status = "error"
        source.last_error = str(exc)[:2000]
        message = source.last_error
    await db.flush()
    return ConnectionTestResponse(status=source.health_status, item_count=count, message=message, checked_at=_now())


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
