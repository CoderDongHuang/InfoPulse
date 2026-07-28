"""Search and saved-search APIs."""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.intelligence import SavedSearch
from app.models.user import User
from app.schemas.search import SavedSearchCreate, SavedSearchResponse, SavedSearchUpdate, SearchResponse
from app.services.search_service import search_contents

router = APIRouter(prefix="/api/v1", tags=["Search"])


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query("", max_length=500), source_ids: list[str] | None = Query(None, alias="sources[]"),
    types: list[str] | None = Query(None, alias="types[]"), regions: list[str] | None = Query(None, alias="regions[]"),
    languages: list[str] | None = Query(None, alias="languages[]"), sentiments: list[str] | None = Query(None, alias="sentiments[]"),
    from_at: datetime | None = Query(None, alias="from"), to_at: datetime | None = Query(None, alias="to"),
    heat_min: int | None = Query(None, ge=0), heat_max: int | None = Query(None, ge=0),
    is_original: bool | None = Query(None), is_official: bool | None = Query(None),
    sort: Literal["relevance", "newest", "heat"] = Query("relevance"), page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100), _user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await search_contents(db, q=q, source_ids=source_ids, types=types, regions=regions, languages=languages,
        sentiments=sentiments, from_at=from_at, to_at=to_at, heat_min=heat_min, heat_max=heat_max,
        is_original=is_original, is_official=is_official, sort=sort, page=page, page_size=page_size)


@router.get("/saved-searches", response_model=list[SavedSearchResponse])
async def list_saved_searches(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return list((await db.scalars(select(SavedSearch).where(SavedSearch.user_id == user.id).order_by(SavedSearch.updated_at.desc()))).all())


@router.post("/saved-searches", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_search(payload: SavedSearchCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    record = SavedSearch(user_id=user.id, **payload.model_dump())
    db.add(record); await db.flush(); return record


async def _owned_search(db: AsyncSession, user_id: str, search_id: str) -> SavedSearch:
    record = await db.scalar(select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user_id))
    if not record: raise HTTPException(status_code=404, detail="保存的搜索不存在")
    return record


@router.patch("/saved-searches/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(search_id: str, payload: SavedSearchUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    record = await _owned_search(db, user.id, search_id)
    for field, value in payload.model_dump(exclude_none=True).items(): setattr(record, field, value)
    record.updated_at = datetime.now(timezone.utc); await db.flush(); return record


@router.delete("/saved-searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(search_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.delete(await _owned_search(db, user.id, search_id))

