"""
InfoPulse — Crawler Base Class
===============================
Abstract base for all platform crawlers (Strategy Pattern).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


@dataclass
class RawPost:
    """A single post/search result from any platform."""
    post_id: str
    title: str
    content: str
    author: str
    publish_time: str
    url: str
    platform: str


@dataclass
class RawComment:
    """A single comment from any platform."""
    comment_id: str
    post_id: str
    content: str
    author: str
    like_count: int = 0
    publish_time: str = ""


class BaseCrawler(ABC):
    """All platform crawlers must implement this interface."""

    platform_name: str = "unknown"

    @abstractmethod
    async def search(self, keyword: str, max_items: int = 50) -> List[RawPost]:
        """Search for posts matching the keyword."""

    @abstractmethod
    async def get_comments(self, post_id: str, max_items: int = 50) -> List[RawComment]:
        """Fetch comments for a given post."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether this crawler is currently usable."""
