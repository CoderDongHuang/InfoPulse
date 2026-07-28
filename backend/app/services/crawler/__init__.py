"""Supported public-opinion source registry.

Only sources used by the product are registered. Additional adapters can still
be developed independently without appearing in the user-facing workflow.
"""

from typing import Type

from app.config import get_settings
from app.services.crawler.base import BaseCrawler
from app.services.crawler.bilibili import BilibiliCrawler
from app.services.crawler.tieba import TiebaCrawler
from app.services.crawler.weibo import WeiboCrawler

CRAWLER_REGISTRY: dict[str, Type[BaseCrawler]] = {
    "weibo": WeiboCrawler,
    "bilibili": BilibiliCrawler,
    "tieba": TiebaCrawler,
}
settings = get_settings()


def get_crawler(platform_name: str) -> BaseCrawler | None:
    if not settings.CRAWLER_ENABLED:
        return None
    crawler_class = CRAWLER_REGISTRY.get(platform_name)
    return crawler_class() if crawler_class else None


def available_platforms() -> list[str]:
    return list(CRAWLER_REGISTRY)
