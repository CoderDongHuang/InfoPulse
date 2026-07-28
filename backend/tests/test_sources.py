"""Contract and persistence tests for real data-source ingestion."""

import unittest

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base
from app.models.intelligence import ContentItem, DataSource
from app.services.collectors.base import NormalizedContent
from app.services.collectors.hacker_news import HackerNewsCollector
from app.services.source_sync import ensure_builtin_sources, sync_source


class HackerNewsCollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_maps_official_api_story(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("topstories.json"):
                return httpx.Response(200, json=[4242])
            return httpx.Response(200, json={
                "id": 4242, "type": "story", "by": "ada", "time": 1700000000,
                "title": "A real HN story", "url": "https://example.com/story",
                "score": 81, "descendants": 13,
            })

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            items = await HackerNewsCollector(client).collect(1)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].external_id, "4242")
        self.assertEqual(items[0].canonical_url, "https://example.com/story")
        self.assertEqual(items[0].like_count, 81)
        self.assertEqual(items[0].comment_count, 13)
        self.assertEqual(items[0].raw_payload["by"], "ada")

    async def test_uses_discussion_url_when_story_has_no_url(self):
        def handler(request: httpx.Request) -> httpx.Response:
            payload = [7] if request.url.path.endswith("topstories.json") else {
                "id": 7, "type": "story", "title": "Ask HN", "by": "lin", "time": 1700000000,
            }
            return httpx.Response(200, json=payload)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            item = (await HackerNewsCollector(client).collect(1))[0]
        self.assertEqual(item.canonical_url, "https://news.ycombinator.com/item?id=7")


class StubCollector:
    def __init__(self, score: int = 10, error: Exception | None = None):
        self.score = score
        self.error = error

    async def collect(self, limit: int):
        if self.error:
            raise self.error
        return [NormalizedContent(
            external_id="101",
            canonical_url="https://example.com/101",
            title="Database story",
            author_name="tester",
            like_count=self.score,
            comment_count=2,
            raw_payload={"id": 101, "score": self.score},
        )]


class SourceSyncTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def _source(self, session) -> DataSource:
        await ensure_builtin_sources(session)
        return await session.scalar(select(DataSource).where(DataSource.key == "hacker-news"))

    async def test_sync_is_idempotent_and_updates_changed_content(self):
        async with self.sessions() as session:
            source = await self._source(session)
            first = await sync_source(session, source, StubCollector(score=10))
            await session.commit()
            self.assertEqual((first.created_count, first.updated_count, first.skipped_count), (1, 0, 0))

            second = await sync_source(session, source, StubCollector(score=10))
            await session.commit()
            self.assertEqual((second.created_count, second.updated_count, second.skipped_count), (0, 0, 1))

            third = await sync_source(session, source, StubCollector(score=11))
            await session.commit()
            self.assertEqual((third.created_count, third.updated_count, third.skipped_count), (0, 1, 0))
            self.assertEqual(await session.scalar(select(func.count(ContentItem.id))), 1)
            item = await session.scalar(select(ContentItem))
            self.assertEqual(item.like_count, 11)

    async def test_failure_is_recorded_without_fake_content(self):
        async with self.sessions() as session:
            source = await self._source(session)
            run = await sync_source(session, source, StubCollector(error=RuntimeError("upstream offline")))
            await session.commit()
            self.assertEqual(run.status, "failed")
            self.assertEqual(run.error_count, 1)
            self.assertIn("upstream offline", run.error_summary)
            self.assertEqual(source.health_status, "error")
            self.assertEqual(await session.scalar(select(func.count(ContentItem.id))), 0)


if __name__ == "__main__":
    unittest.main()
