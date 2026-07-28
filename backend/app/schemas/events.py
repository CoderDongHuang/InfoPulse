"""Event workflow request and response contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ClusterRequest(BaseModel):
    hours: int = Field(168, ge=1, le=720)
    threshold: float = Field(0.24, ge=0.05, le=0.9)


class ClusterResponse(BaseModel):
    scanned_count: int
    created_count: int
    event_ids: list[str]


class EventCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=500)
    category: str = Field(default="uncategorized", min_length=1, max_length=80)
    content_ids: list[str] = Field(min_length=1, max_length=200)


class EventUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=500)
    category: str | None = Field(None, min_length=1, max_length=80)
    status: Literal["detected", "rising", "responded", "closed"] | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    risk_notes: str | None = Field(None, max_length=4000)


class EventMergeRequest(BaseModel):
    target_event_id: str
    source_event_ids: list[str] = Field(min_length=1, max_length=50)
    keep_title: str | None = Field(None, min_length=2, max_length=500)

    @model_validator(mode="after")
    def target_not_in_sources(self):
        if self.target_event_id in self.source_event_ids:
            raise ValueError("目标事件不能同时作为来源事件")
        self.source_event_ids = list(dict.fromkeys(self.source_event_ids))
        return self
