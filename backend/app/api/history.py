"""Unified history endpoints for generated user workflows."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.analysis_history import AnalysisHistory
from app.models.user import User

router = APIRouter(prefix="/api/v1/history", tags=["History"])
HistoryModule = Literal["insight", "mouthpiece", "timeline"]


@router.get("")
async def list_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    module: HistoryModule | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filters = [AnalysisHistory.user_id == current_user.id]
    if module:
        filters.append(AnalysisHistory.module == module)
    rows = await db.execute(
        select(AnalysisHistory)
        .where(*filters)
        .order_by(AnalysisHistory.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    count = await db.execute(select(func.count(AnalysisHistory.id)).where(*filters))
    return {
        "items": [
            {
                "id": row.id,
                "module": row.module,
                "input_params": row.input_params,
                "output_result": row.output_result,
                "status": row.status,
                "created_at": row.created_at,
            }
            for row in rows.scalars().all()
        ],
        "total": count.scalar() or 0,
        "page": page,
    }


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_history(
    record_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        delete(AnalysisHistory).where(
            AnalysisHistory.id == record_id,
            AnalysisHistory.user_id == current_user.id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="记录不存在")
    await db.commit()
