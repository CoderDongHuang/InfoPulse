"""Event workflow request and response contracts."""

from pydantic import BaseModel, Field


class ClusterRequest(BaseModel):
    hours: int = Field(168, ge=1, le=720)
    threshold: float = Field(0.24, ge=0.05, le=0.9)


class ClusterResponse(BaseModel):
    scanned_count: int
    created_count: int
    event_ids: list[str]

