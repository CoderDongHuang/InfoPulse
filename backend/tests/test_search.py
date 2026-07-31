"""Database search and saved-search contract tests."""

import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base
from app.main import app
from app.models.intelligence import ContentItem, DataSource
from app.services.search_service import search_contents


class SearchServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def _seed(self, session):
        source = DataSource(key="search-source", name="Search Source", source_type="official_api")
        session.add(source); await session.flush()
        session.add_all([
            ContentItem(source_id=source.id, external_id="1", canonical_url="https://example.com/ai",
                title="OpenAI launches agent tools", body="Developers can build reliable agents.", content_type="article",
                language="en", region="global", sentiment="positive", tags=["AI"], entities=["OpenAI"],
                is_original=True, is_official=True, like_count=50, comment_count=10, content_hash="a" * 64,
                published_at=datetime.now(timezone.utc)),
            ContentItem(source_id=source.id, external_id="2", canonical_url="https://example.com/java",
                title="Java runtime update", body="Performance release.", content_type="article", language="en",
                region="global", sentiment="neutral", tags=["Java"], entities=["Java"], is_original=True,
                is_official=False, like_count=2, content_hash="b" * 64,
                published_at=datetime.now(timezone.utc) - timedelta(days=1)),
        ])
        await session.commit()
        return source

    async def test_keyword_filters_and_heat_sort_use_database_rows(self):
        async with self.sessions() as session:
            source = await self._seed(session)
            result = await search_contents(session, q="agent", source_ids=[source.id], languages=["en"],
                sentiments=["positive"], is_official=True, sort="heat", page=1, page_size=10)
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["items"][0]["title"], "OpenAI launches agent tools")
            self.assertEqual(result["items"][0]["canonical_url"], "https://example.com/ai")
            self.assertGreater(result["items"][0]["heat"], 50)

    async def test_search_pagination_has_more(self):
        async with self.sessions() as session:
            await self._seed(session)
            first = await search_contents(session, sort="newest", page=1, page_size=1)
            second = await search_contents(session, sort="newest", page=2, page_size=1)
            self.assertTrue(first["has_more"])
            self.assertFalse(second["has_more"])
            self.assertNotEqual(first["items"][0]["id"], second["items"][0]["id"])


class SearchApiContractTests(unittest.TestCase):
    def test_search_content_and_saved_search_routes_are_protected(self):
        routes = {(route.path, method) for route in app.routes for method in (getattr(route, "methods", None) or set())}
        expected = {
            ("/api/v1/search", "GET"), ("/api/v1/contents/{content_id}", "GET"),
            ("/api/v1/saved-searches", "GET"), ("/api/v1/saved-searches", "POST"),
            ("/api/v1/saved-searches/{search_id}", "PATCH"), ("/api/v1/saved-searches/{search_id}", "DELETE"),
        }
        self.assertTrue(expected.issubset(routes))
        self.assertIn(TestClient(app).get("/api/v1/search").status_code, (401, 403))


if __name__ == "__main__":
    unittest.main()
