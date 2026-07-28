"""Search, content detail, and saved-search contracts."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SearchResultItem(BaseModel):
    id: str
    title: str
    summary: str
    source: dict
    author: str
    published_at: datetime | None
    heat: int
    sentiment: str
    tags: list
    event: dict | None
    canonical_url: str
    content_type: str
    language: str
    region: str
    is_original: bool | None
    is_official: bool


class SearchResponse(BaseModel):
    items: list[SearchResultItem]
    page: int
    page_size: int
    total: int
    has_more: bool


class SavedSearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    query: str = Field(default="", max_length=500)
    filters: dict[str, Any] = Field(default_factory=dict)


class SavedSearchUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    query: str | None = Field(None, max_length=500)
    filters: dict[str, Any] | None = None


class SavedSearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    query: str
    filters: dict
    created_at: datetime
    updated_at: datetime

