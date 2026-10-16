"""Behavioral regressions for scheduled real-data ingestion and discovery."""
import asyncio
from datetime import timedelta
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.core.database import Base
from app.core.errors import AppError
from app.models.intelligence import ContentItem, DataSource, SyncRun
from app.services.source_sync import ensure_builtin_sources, source_is_due, sync_due_sources, sync_source, utc_now
from app.services.stage3 import discover_data, workspace_data
from tests import test_sources
from tests.test_sources import StubCollector


class PublicPipelineTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_sources.SourceSyncTests.asyncSetUp
    asyncTearDown = test_sources.SourceSyncTests.asyncTearDown
    _source = test_sources.SourceSyncTests._source
    async def test_scheduled_sync_skips_disabled_and_not_due_and_continues_after_failure(self):
        async with self.sessions() as db:
            await ensure_builtin_sources(db)
            await ensure_builtin_sources(db)
            sources = {s.key: s for s in (await db.scalars(select(DataSource))).all()}
            sources['arxiv'].enabled = False
            sources['devto'].last_sync_at = utc_now()
            await db.commit()
        runs = await sync_due_sources(self.sessions, lambda s: StubCollector(error=RuntimeError('offline') if s.key == 'github' else None))
        self.assertEqual(len(runs), 2)
        self.assertEqual(sorted(r.status for r in runs), ['failed', 'succeeded'])
        self.assertTrue(all(r.trigger_type == 'scheduled' for r in runs))
        self.assertEqual(await sync_due_sources(self.sessions, lambda _: StubCollector()), [])
        async with self.sessions() as db:
            self.assertEqual(await db.scalar(select(func.count(ContentItem.id))), 1)
            self.assertEqual(await db.scalar(select(func.count(SyncRun.id))), 2)

    async def test_stale_claim_rejected_before_ingestion(self):
        # Two independent file DB connections: an in-flight fetch must not hold
        # SQLite's write lock, and its stale snapshot must not ingest afterward.
        with tempfile.TemporaryDirectory() as folder:
            engine = create_async_engine('sqlite+aiosqlite:///' + (Path(folder) / 'race.db').as_posix())
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            started, release = asyncio.Event(), asyncio.Event()
            class WaitingCollector:
                async def collect(self, limit):
                    started.set()
                    await release.wait()
                    return await StubCollector().collect(limit)
            try:
                async with engine.begin() as connection:
                    await connection.run_sync(Base.metadata.create_all)
                async with sessions() as db:
                    source = await self._source(db)
                    await db.commit()
                    pending = asyncio.create_task(sync_source(db, source, WaitingCollector()))
                    try:
                        await asyncio.wait_for(started.wait(), 5)
                        async def other_writer():
                            async with sessions() as writer:
                                await writer.execute(update(DataSource).where(DataSource.id == source.id).values(last_sync_at=utc_now()))
                                await writer.commit()
                        await asyncio.wait_for(other_writer(), 5)
                    finally:
                        release.set()
                    with self.assertRaises(AppError):
                        await pending
                    self.assertEqual(await db.scalar(select(func.count(ContentItem.id))), 0)
            finally:
                await engine.dispose()

    async def test_collect_timeout_records_failure(self):
        class SlowCollector:
            async def collect(self, limit):
                await asyncio.sleep(5)
        async with self.sessions() as db:
            source = await self._source(db)
            with patch('app.services.source_sync.get_settings') as settings:
                settings.return_value.SOURCE_SYNC_TIMEOUT_SECONDS = .01
                run = await sync_source(db, source, SlowCollector())
            await db.commit()
            self.assertEqual(run.status, 'failed')
            self.assertIn('超时', run.error_summary)
            self.assertEqual(await db.scalar(select(func.count(ContentItem.id))), 0)

    async def test_due_boundary_and_disabled(self):
        source = DataSource(enabled=True, sync_interval_minutes=30, last_sync_at=utc_now() - timedelta(minutes=31))
        self.assertTrue(source_is_due(source, utc_now()))
        source.enabled = False
        self.assertFalse(source_is_due(source, utc_now()))

    async def test_invalid_batch_rolls_back_contents_but_keeps_failed_run(self):
        class InvalidCollector:
            async def collect(self, limit):
                items = await StubCollector().collect(limit)
                from dataclasses import replace
                return [items[0], replace(items[0], external_id='invalid', canonical_url=None)]
        async with self.sessions() as db:
            source = await self._source(db)
            run = await sync_source(db, source, InvalidCollector())
            await db.commit()
            self.assertEqual(run.status, 'failed')
            self.assertEqual(run.created_count, 0)
            self.assertEqual(await db.scalar(select(func.count(ContentItem.id))), 0)
            self.assertEqual(await db.scalar(select(func.count(SyncRun.id))), 1)

    async def test_undated_non_ai_content_reaches_all_channel_and_workspace(self):
        async with self.sessions() as db:
            source = await self._source(db)
            await sync_source(db, source, StubCollector())
            await db.commit()
            await db.refresh(source)
            from app.schemas.sources import DataSourceResponse
            self.assertTrue(DataSourceResponse.model_validate(source).model_dump(mode='json')['last_sync_at'].endswith('Z'))
            found = await discover_data(db, 'public-reader', 'all', 'week')
            self.assertEqual(found['total'], 1)
            self.assertIsNone(found['items'][0]['published_at'])
            self.assertEqual((await workspace_data(db, 'public-reader'))['recommendations'][0]['id'], found['items'][0]['id'])
            self.assertEqual((await discover_data(db, 'public-reader', 'ai', 'week'))['total'], 0)


if __name__ == '__main__':
    unittest.main()
