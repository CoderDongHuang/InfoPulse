"""Cross-platform hot ranking endpoints."""

from fastapi import APIRouter

from app.schemas.workflows import HotItemRequest
from app.services.workflows import explain_hot_item, fetch_hot_ranking_payload

router = APIRouter(prefix="/api/v1/hot-search", tags=["Hot Search"])


@router.get("/ranking")
async def ranking():
    return await fetch_hot_ranking_payload()


@router.post("/explain")
async def explain(item: HotItemRequest):
    return {"explanation": await explain_hot_item(item.model_dump())}
