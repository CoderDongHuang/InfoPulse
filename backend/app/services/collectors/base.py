"""Contracts shared by real third-party content collectors."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(slots=True)
class NormalizedContent:
    external_id: str
    canonical_url: str
    title: str
    body: str = ""
    author_name: str = ""
    author_external_id: str = ""
    content_type: str = "article"
    language: str = "und"
    region: str = ""
    published_at: datetime | None = None
    view_count: int | None = None
    comment_count: int | None = None
    like_count: int | None = None
    share_count: int | None = None
    is_official: bool = False
    is_original: bool | None = None
    raw_payload: dict = field(default_factory=dict)


class ContentCollector(Protocol):
    async def collect(self, limit: int) -> list[NormalizedContent]: ...

