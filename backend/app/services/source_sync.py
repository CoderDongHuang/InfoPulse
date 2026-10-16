"""Source registry and idempotent ingestion orchestration."""

import asyncio
import hashlib
import logging
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
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
    # Atomic registration: API requests and the worker may start simultaneously.
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    for key, name, source_type, base_url, interval in BUILTIN_SOURCES:
        await db.execute(insert(DataSource).values(
            key=key, name=name, source_type=source_type, base_url=base_url,
            config={"max_items": 30}, sync_interval_minutes=interval,
        ).on_conflict_do_nothing(index_elements=["key"]))


async def sync_source(db: AsyncSession, source: DataSource, collector=None, *, trigger_type="manual") -> SyncRun:
    if not source.enabled:
        raise AppError("SOURCE_DISABLED", "数据源已停用", 409)
    if source.key not in {item[0] for item in BUILTIN_SOURCES} and source.source_type != "rss":
        raise AppError("SOURCE_NOT_SUPPORTED", "该数据源尚未配置采集器", 409)

    # Fetch before taking a write lock: an offline upstream must not prevent
    # registrations, favorites or the scheduler from writing to local SQLite.
    # Competing workers may fetch the same page, but only one can ingest it.
    collection_error = None
    items = []
    try:
        active_collector = collector or collector_for(source)
        limit = min(max(int(source.config.get("max_items", 30)), 1), 100)
        items = await asyncio.wait_for(active_collector.collect(limit), get_settings().SOURCE_SYNC_TIMEOUT_SECONDS)
    except Exception as exc:
        collection_error = exc
    # Compare-and-set serializes ingestion in both supported DBs. The claim
    # and content commit atomically; process death cannot strand a running lease.
    started = utc_now()
    claimed = await db.execute(update(DataSource).where(
        DataSource.id == source.id, DataSource.enabled.is_(True),
        DataSource.last_sync_at == source.last_sync_at,
    ).values(last_sync_at=started).execution_options(synchronize_session=False))
    if claimed.rowcount != 1:
        raise AppError("SOURCE_BUSY", "该来源已被其他同步任务处理，请刷新后重试", 409)
    source.last_sync_at = started
    run = SyncRun(
        source_id=source.id,
        trigger_type=trigger_type,
        status="running",
        started_at=started,
        diagnostic_id=str(uuid.uuid4()),
    )
    db.add(run)
    source.last_sync_at = run.started_at
    await db.flush()

    try:
        if collection_error is not None:
            raise collection_error
        run.fetched_count = len(items)
        # A malformed batch rolls back content only, preserving its failed run.
        async with db.begin_nested():
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
            await db.flush()
        run.status = "succeeded"
        source.health_status = "healthy"
        source.last_success_at = utc_now()
        source.last_error = None
    except Exception as exc:
        await db.refresh(run)
        run.status = "failed"
        run.created_count = run.updated_count = run.skipped_count = 0
        run.error_count = 1
        run.error_summary = ("采集超时，请检查网络或稍后重试" if isinstance(exc, asyncio.TimeoutError) else str(exc))[:2000]
        source.health_status = "error"
        source.last_error = run.error_summary
    finally:
        run.finished_at = utc_now()
        await db.flush()
    return run


def source_is_due(source: DataSource, now: datetime) -> bool:
    if not source.enabled:
        return False
    previous = source.last_sync_at
    if previous is None:
        return True
    if previous.tzinfo is None:
        previous = previous.replace(tzinfo=timezone.utc)
    return previous + timedelta(minutes=max(1, source.sync_interval_minutes)) <= now


async def sync_due_sources(session_factory=None, collector_factory=None) -> list[SyncRun]:
    from app.core.database import _get_sessionmaker
    sessions = session_factory or _get_sessionmaker()
    async with sessions() as db:
        await ensure_builtin_sources(db)
        await db.commit()
        ids = list((await db.scalars(select(DataSource.id).where(DataSource.enabled.is_(True)))).all())
    completed = []
    for source_id in ids:
        try:
            async with sessions() as db:
                source = await db.get(DataSource, source_id)
                if source is None or not source_is_due(source, utc_now()):
                    continue
                run = await sync_source(db, source, collector_factory(source) if collector_factory else None, trigger_type="scheduled")
                await db.commit()
                completed.append(run)
        except Exception:
            logging.getLogger(__name__).exception("Source sync failed source_id=%s", source_id)
    return completed


async def source_sync_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await sync_due_sources()
        except Exception:
            logging.getLogger(__name__).exception("Source sync iteration failed")
        try:
            await asyncio.wait_for(stop.wait(), get_settings().SOURCE_SYNC_POLL_SECONDS)
        except asyncio.TimeoutError:
            pass


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
