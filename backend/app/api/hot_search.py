"""Cross-platform hot ranking endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.workflows import HotItemRequest
from app.services.content_feed import fetch_intelligence_ranking
from app.services.workflows import explain_hot_item

router = APIRouter(prefix="/api/v1/hot-search", tags=["Hot Search"])


@router.get("/ranking")
async def ranking(db: AsyncSession = Depends(get_db)):
    return await fetch_intelligence_ranking(db)


@router.post("/explain")
async def explain(item: HotItemRequest):
    return {"explanation": await explain_hot_item(item.model_dump())}
