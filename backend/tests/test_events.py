"""Tests for deterministic event clustering and explainable scores."""

import unittest
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base
from app.models.intelligence import AuditLog, ContentItem, DataSource, Event, EventContent, EventEntity
from app.models.user import User
from app.services.event_clustering import cluster_recent_content, event_scores, similarity
from app.services.event_service import create_manual_event, merge_events, update_manual_event


class EventClusteringTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection: await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self): await self.engine.dispose()

    async def _seed(self, session):
        github = DataSource(key="event-github", name="GitHub", source_type="official_api")
        news = DataSource(key="event-news", name="News", source_type="rss")
        session.add_all([github, news]); await session.flush()
        now = datetime.now(timezone.utc)
        rows = [
            ContentItem(source_id=github.id, external_id="1", canonical_url="https://github.com/openai/sdk",
                title="OpenAI releases new Agent SDK", body="OpenAI Agent SDK improves tool orchestration",
                content_type="repository", language="en", region="global", entities=["OpenAI", "Agent SDK"],
                sentiment="positive", like_count=100, comment_count=20, content_hash="1" * 64, published_at=now),
            ContentItem(source_id=news.id, external_id="2", canonical_url="https://news.example/openai-agent-sdk",
                title="OpenAI Agent SDK released for developers", body="The new Agent SDK from OpenAI is available",
                content_type="article", language="en", region="global", entities=["OpenAI", "Agent SDK"],
                sentiment="neutral", like_count=30, comment_count=8, content_hash="2" * 64, published_at=now),
            ContentItem(source_id=news.id, external_id="3", canonical_url="https://news.example/security",
                title="Cloud service breach and outage", body="Security attack caused a serious data breach and outage",
                content_type="article", language="en", region="global", entities=["Cloud"], sentiment="negative",
                like_count=10, content_hash="3" * 64, published_at=now),
        ]
        session.add_all(rows); await session.commit(); return rows

    async def test_clusters_similar_cross_source_content_and_is_repeatable(self):
        async with self.sessions() as session:
            rows = await self._seed(session)
            self.assertGreater(similarity(rows[0], rows[1]), 0.24)
            first = await cluster_recent_content(session); await session.commit()
            second = await cluster_recent_content(session); await session.commit()
            self.assertEqual(first["created_count"], 2)
            self.assertEqual(second["created_count"], 0)
            self.assertEqual(await session.scalar(select(func.count(Event.id))), 2)
            grouped = await session.scalar(select(Event).where(Event.title.contains("Agent SDK")))
            links = await session.scalar(select(func.count(EventContent.content_item_id)).where(EventContent.event_id == grouped.id))
            self.assertEqual(links, 2)
            self.assertGreater(grouped.confidence, 60)
            self.assertGreater(await session.scalar(select(func.count(EventEntity.id)).where(EventEntity.event_id == grouped.id)), 0)

    async def test_risk_score_uses_visible_risk_signals(self):
        async with self.sessions() as session:
            rows = await self._seed(session)
            _heat, risk, _confidence = event_scores([rows[2]], 1)
            self.assertGreaterEqual(risk, 40)

    async def test_manual_create_update_and_merge_are_locked_and_audited(self):
        async with self.sessions() as session:
            rows = await self._seed(session)
            user = User(username="editor", email="editor@example.com", password_hash="hash")
            session.add(user); await session.flush()
            target = await create_manual_event(session, user.id, "Agent SDK launch", "technology", [rows[0].id])
            source = await create_manual_event(session, user.id, "SDK developer coverage", "technology", [rows[1].id])
            await update_manual_event(session, user.id, target, {"risk_notes": "Monitor adoption", "status": "responded"})
            await merge_events(session, user.id, target, [source.id], "OpenAI Agent SDK launch")
            await session.commit()
            self.assertTrue(target.manual_locked)
            self.assertEqual(target.title, "OpenAI Agent SDK launch")
            self.assertEqual(await session.scalar(select(func.count(EventContent.content_item_id)).where(EventContent.event_id == target.id)), 2)
            self.assertIsNotNone(source.deleted_at)
            self.assertEqual(await session.scalar(select(func.count(AuditLog.id)).where(AuditLog.target_id == target.id)), 3)
            rerun = await cluster_recent_content(session); await session.commit()
            self.assertNotIn(target.id, rerun["event_ids"])


if __name__ == "__main__": unittest.main()
