"""Data source and synchronization API contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class DataSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    key: str
    name: str
    source_type: str
    base_url: str
    enabled: bool
    health_status: str
    sync_interval_minutes: int
    last_sync_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None


class SyncRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    trigger_type: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    fetched_count: int
    created_count: int
    updated_count: int
    skipped_count: int
    error_count: int
    error_summary: str | None
    diagnostic_id: str | None
    created_at: datetime


class SourceUpdateRequest(BaseModel):
    enabled: bool | None = None
    sync_interval_minutes: int | None = Field(None, ge=5, le=10080)


class RssSourceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    feed_url: HttpUrl
    sync_interval_minutes: int = Field(60, ge=15, le=10080)


class RssValidateRequest(BaseModel):
    feed_url: HttpUrl


class ConnectionTestResponse(BaseModel):
    status: str
    item_count: int = 0
    message: str
    checked_at: datetime
