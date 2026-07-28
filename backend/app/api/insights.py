"""Hot-topic insight API with reliable SSE heartbeats."""

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.analysis_history import AnalysisHistory
from app.models.user import User
from app.schemas.workflows import InsightRequest
from app.services.workflows import analyze_insight, collect_posts

router = APIRouter(prefix="/api/v1/insights", tags=["Hot Topic Insights"])
logger = logging.getLogger(__name__)


def _sse(event: str, payload) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/analyze")
async def analyze(
    payload: InsightRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()

    async def producer():
        try:
            await queue.put(("progress", {"stage": "collecting", "message": "正在汇集公开讨论", "percent": 12}))
            posts, sources = await collect_posts(payload.keyword, payload.platforms, payload.max_items)
            await queue.put(("progress", {
                "stage": "analyzing",
                "message": f"已获取 {len(posts)} 条有效样本，正在识别情绪与观点",
                "percent": 62,
                "sources": sources,
            }))
            if not posts:
                await queue.put(("error", {"message": "暂未找到有效公开讨论，请更换关键词后重试"}))
                return
            result = await analyze_insight(payload.keyword, posts, sources)
            history = AnalysisHistory(
                user_id=current_user.id,
                module="insight",
                input_params=payload.model_dump(),
                output_result=result,
                status="completed",
                created_at=datetime.now(timezone.utc),
            )
            db.add(history)
            await db.commit()
            result["history_id"] = history.id
            await queue.put(("progress", {"stage": "done", "message": "洞察报告已生成", "percent": 100}))
            await queue.put(("result", result))
        except Exception:
            logger.exception("Insight workflow failed for user %s", current_user.id)
            await queue.put(("error", {"message": "分析暂时失败，请稍后重试"}))
        finally:
            await queue.put(("close", None))

    async def stream():
        task = asyncio.create_task(producer())
        try:
            while True:
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=5)
                except asyncio.TimeoutError:
                    yield _sse("ping", {"ts": datetime.now(timezone.utc).isoformat()})
                    continue
                if event == "close":
                    break
                yield _sse(event, data)
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/history")
async def history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filters = (AnalysisHistory.user_id == current_user.id, AnalysisHistory.module == "insight")
    rows = await db.execute(
        select(AnalysisHistory).where(*filters).order_by(AnalysisHistory.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    count = await db.execute(select(func.count(AnalysisHistory.id)).where(*filters))
    return {
        "items": [
            {"id": row.id, "input_params": row.input_params, "output_result": row.output_result, "status": row.status, "created_at": row.created_at}
            for row in rows.scalars().all()
        ],
        "total": count.scalar() or 0,
        "page": page,
    }


@router.delete("/history/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_history(record_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(AnalysisHistory).where(AnalysisHistory.id == record_id, AnalysisHistory.user_id == current_user.id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="记录不存在")
    await db.commit()
