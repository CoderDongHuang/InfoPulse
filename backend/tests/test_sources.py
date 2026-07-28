"""Contract and persistence tests for real data-source ingestion."""

import unittest

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base
from app.models.intelligence import ContentItem, DataSource
from app.services.collectors.base import NormalizedContent
from app.services.collectors.hacker_news import HackerNewsCollector
from app.services.collectors.github import GitHubCollector
from app.services.collectors.devto import DevToCollector
from app.services.collectors.arxiv import ArxivCollector
from app.services.collectors.rss import RssCollector, validate_public_feed_url
from app.services.source_sync import ensure_builtin_sources, sync_source
from app.main import app
from app.schemas.sources import RssSourceRequest


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


class OfficialCollectorContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_github_maps_repository_metrics(self):
        payload = {"items": [{
            "id": 9, "html_url": "https://github.com/acme/agent", "full_name": "acme/agent",
            "description": "Agent toolkit", "owner": {"login": "acme", "id": 2},
            "created_at": "2026-07-28T01:02:03Z", "stargazers_count": 44,
            "forks_count": 5, "open_issues_count": 3,
        }]}
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))) as client:
            item = (await GitHubCollector(client).collect(1))[0]
        self.assertEqual(item.content_type, "repository")
        self.assertEqual((item.like_count, item.share_count, item.comment_count), (44, 5, 3))

    async def test_devto_maps_article(self):
        payload = [{
            "id": 8, "canonical_url": "https://dev.to/ada/post", "title": "Build an agent",
            "description": "A practical guide", "published_at": "2026-07-28T01:02:03Z",
            "comments_count": 4, "positive_reactions_count": 20,
            "user": {"name": "Ada", "username": "ada", "user_id": 1},
        }]
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))) as client:
            item = (await DevToCollector(client).collect(1))[0]
        self.assertEqual(item.author_name, "Ada")
        self.assertEqual(item.like_count, 20)

    async def test_arxiv_maps_atom_entry(self):
        atom = b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
        <entry><id>https://arxiv.org/abs/2607.12345v1</id><title> Useful AI Paper </title>
        <summary> Research summary </summary><published>2026-07-28T01:02:03Z</published>
        <author><name>Ada Lovelace</name></author><category term="cs.AI"/></entry></feed>'''
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=atom))) as client:
            item = (await ArxivCollector(client).collect(1))[0]
        self.assertEqual(item.external_id, "2607.12345v1")
        self.assertEqual(item.content_type, "paper")

    async def test_rss_maps_rss_and_atom(self):
        rss = b'''<rss version="2.0"><channel><item><guid>post-1</guid><title>Feed item</title>
        <link>https://example.com/post-1</link><description>Summary</description>
        <pubDate>Tue, 28 Jul 2026 10:00:00 GMT</pubDate></item></channel></rss>'''
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=rss))) as client:
            item = (await RssCollector("https://example.com/feed.xml", client).collect(1))[0]
        self.assertEqual(item.external_id, "post-1")
        self.assertEqual(item.title, "Feed item")

    def test_rss_rejects_private_networks(self):
        for url in ("http://127.0.0.1/feed", "http://localhost/rss", "http://10.0.0.4/feed"):
            with self.assertRaises(ValueError):
                validate_public_feed_url(url, resolve_dns=False)


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


class SourceApiContractTests(unittest.TestCase):
    def test_management_routes_are_registered_and_protected(self):
        routes = {(route.path, method) for route in app.routes for method in (route.methods or set())}
        expected = {
            ("/api/v1/sources", "GET"), ("/api/v1/sources/{source_id}", "GET"),
            ("/api/v1/sources/{source_id}", "PATCH"), ("/api/v1/sources/{source_id}/test", "POST"),
            ("/api/v1/sources/{source_id}/sync", "POST"),
            ("/api/v1/sources/{source_id}/sync-runs", "GET"),
            ("/api/v1/sources/rss/validate", "POST"), ("/api/v1/sources/rss", "POST"),
        }
        self.assertTrue(expected.issubset(routes))
        response = TestClient(app).get("/api/v1/sources")
        self.assertIn(response.status_code, (401, 403))

    def test_rss_request_normalizes_url(self):
        payload = RssSourceRequest(name="Python", feed_url="https://example.com/feed.xml")
        self.assertEqual(str(payload.feed_url), "https://example.com/feed.xml")


if __name__ == "__main__":
    unittest.main()
