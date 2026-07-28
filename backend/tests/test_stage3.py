import unittest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.core.database import Base
import app.models  # noqa
from app.models.intelligence import ContentItem, DataSource, RecommendationFeedback, WatchTopic
from app.models.user import User
from app.services.stage3 import dashboard_data, discover_data, workspace_data
from app.services.stage3 import keyword_matches

class Stage3ServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_ascii_keywords_use_word_boundaries(self):
        self.assertTrue(keyword_matches("ai", "new AI model"))
        self.assertFalse(keyword_matches("ai", "personal details"))
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
    async def asyncTearDown(self): await self.engine.dispose()

    async def test_empty_state_never_creates_recommendations(self):
        async with self.sessions() as db:
            user = User(username="empty", email="empty@example.com", password_hash="x"); db.add(user); await db.flush()
            dashboard = await dashboard_data(db); discover = await discover_data(db, user.id); workspace = await workspace_data(db, user.id)
            self.assertFalse(dashboard["has_data"]); self.assertEqual(discover["items"], []); self.assertEqual(workspace["recommendations"], [])
            self.assertTrue(workspace["source_warnings"])

    async def test_real_content_is_ranked_with_explanation_and_feedback_hides_it(self):
        async with self.sessions() as db:
            user = User(username="reader", email="reader@example.com", password_hash="x")
            source = DataSource(key="hn", name="Hacker News", source_type="hacker_news", health_status="healthy")
            db.add_all([user, source]); await db.flush()
            item = ContentItem(source_id=source.id, external_id="1", canonical_url="https://news.ycombinator.com/item?id=1", title="OpenAI launches a new AI agent", body="Open source agent tooling", content_type="article", language="en", content_hash="a"*64, published_at=datetime.now(timezone.utc), comment_count=40)
            db.add_all([item, WatchTopic(user_id=user.id, name="OpenAI", keywords=["agent"])]); await db.flush()
            result = await discover_data(db, user.id)
            self.assertEqual(result["total"], 1); self.assertTrue(result["items"][0]["recommendation_reasons"])
            dashboard = await dashboard_data(db); self.assertEqual(dashboard["metrics"]["content"], 1)
            db.add(RecommendationFeedback(user_id=user.id, target_type="content", target_id=item.id, feedback_type="not_interested")); await db.flush()
            self.assertEqual((await discover_data(db, user.id))["items"], [])
