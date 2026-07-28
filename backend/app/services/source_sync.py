"""Source registry and idempotent ingestion orchestration."""

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.intelligence import ContentItem, DataSource, SyncRun
from app.config import get_settings
from app.services.collectors import (
    ArxivCollector, DevToCollector, GitHubCollector, HackerNewsCollector, NormalizedContent, RssCollector,
)

HACKER_NEWS_KEY = "hacker-news"
BUILTIN_SOURCES = (
    (HACKER_NEWS_KEY, "Hacker News", "official_api", HackerNewsCollector.base_url, 30),
    ("github", "GitHub", "official_api", GitHubCollector.base_url, 30),
    ("devto", "DEV Community", "official_api", DevToCollector.base_url, 60),
    ("arxiv", "arXiv", "official_api", ArxivCollector.base_url, 120),
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def content_hash(item: NormalizedContent) -> str:
    stable = {
        "canonical_url": item.canonical_url,
        "title": item.title,
        "body": item.body,
        "author_name": item.author_name,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "comment_count": item.comment_count,
        "like_count": item.like_count,
    }
    return hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


async def ensure_builtin_sources(db: AsyncSession) -> None:
    keys = set((await db.scalars(select(DataSource.key).where(DataSource.key.in_([item[0] for item in BUILTIN_SOURCES])))).all())
    for key, name, source_type, base_url, interval in BUILTIN_SOURCES:
        if key not in keys:
            db.add(DataSource(
                key=key, name=name, source_type=source_type, base_url=base_url,
                config={"max_items": 30}, sync_interval_minutes=interval,
            ))
    if len(keys) != len(BUILTIN_SOURCES):
        await db.flush()


async def sync_source(db: AsyncSession, source: DataSource, collector=None) -> SyncRun:
    if not source.enabled:
        raise AppError("SOURCE_DISABLED", "数据源已停用", 409)
    if source.key not in {item[0] for item in BUILTIN_SOURCES} and source.source_type != "rss":
        raise AppError("SOURCE_NOT_SUPPORTED", "该数据源尚未配置采集器", 409)

    run = SyncRun(
        source_id=source.id,
        trigger_type="manual",
        status="running",
        started_at=utc_now(),
        diagnostic_id=str(uuid.uuid4()),
    )
    db.add(run)
    source.last_sync_at = run.started_at
    await db.flush()

    try:
        active_collector = collector or collector_for(source)
        limit = min(max(int(source.config.get("max_items", 30)), 1), 100)
        items = await active_collector.collect(limit)
        run.fetched_count = len(items)
        for item in items:
            digest = content_hash(item)
            existing = await db.scalar(
                select(ContentItem).where(
                    ContentItem.source_id == source.id,
                    ContentItem.external_id == item.external_id,
                )
            )
            if existing is None:
                db.add(_new_content(source.id, item, digest))
                run.created_count += 1
            elif existing.content_hash == digest:
                existing.fetched_at = utc_now()
                existing.raw_payload = item.raw_payload
                run.skipped_count += 1
            else:
                _update_content(existing, item, digest)
                run.updated_count += 1
        run.status = "succeeded"
        source.health_status = "healthy"
        source.last_success_at = utc_now()
        source.last_error = None
    except Exception as exc:
        run.status = "failed"
        run.error_count = 1
        run.error_summary = str(exc)[:2000]
        source.health_status = "error"
        source.last_error = run.error_summary
    finally:
        run.finished_at = utc_now()
        await db.flush()
    return run


def collector_for(source: DataSource):
    if source.key == HACKER_NEWS_KEY:
        return HackerNewsCollector()
    if source.key == "github":
        return GitHubCollector(token=get_settings().GITHUB_TOKEN)
    if source.key == "devto":
        return DevToCollector()
    if source.key == "arxiv":
        return ArxivCollector()
    if source.source_type == "rss":
        return RssCollector(str(source.config.get("feed_url") or source.base_url))
    raise AppError("SOURCE_NOT_SUPPORTED", "该数据源尚未配置采集器", 409)


async def test_source_connection(source: DataSource) -> int:
    collector = collector_for(source)
    items = await collector.collect(1)
    return len(items)


def _new_content(source_id: str, item: NormalizedContent, digest: str) -> ContentItem:
    content = ContentItem(source_id=source_id, external_id=item.external_id, content_hash=digest)
    _update_content(content, item, digest)
    return content


def _update_content(content: ContentItem, item: NormalizedContent, digest: str) -> None:
    for field in (
        "canonical_url", "title", "body", "author_name", "author_external_id", "content_type",
        "language", "region", "published_at", "view_count", "comment_count", "like_count",
        "share_count", "is_official", "is_original", "raw_payload",
    ):
        setattr(content, field, getattr(item, field))
    content.content_hash = digest
    content.fetched_at = utc_now()
