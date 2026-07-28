import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.core.database import Base
from app.models.intelligence import AgentTask, ContentItem, DataSource, Notification, NotificationPreference, Report, TaskRun
from app.models.user import User
from app.services.automation import create_notification, enqueue_run, next_run, validate_webhook_url


class AutomationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection: await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self): await self.engine.dispose()

    async def test_daily_report_uses_real_content_and_keeps_idempotency(self):
        async with self.sessions() as db:
            user = User(username="automation", email="automation@example.com", password_hash="x")
            source = DataSource(key="automation-source", name="Official source", source_type="rss")
            db.add_all([user, source]); await db.flush()
            item = ContentItem(source_id=source.id, external_id="a1", canonical_url="https://example.com/a1", title="Verified product release", body="Official evidence", content_type="article", content_hash="a" * 64, fetched_at=datetime.now(timezone.utc), published_at=datetime.now(timezone.utc))
            task = AgentTask(user_id=user.id, name="Daily", task_type="daily_report", config={"query": "release", "channels": ["in_app"]}, schedule={"kind": "daily", "time": "09:00"}, timezone="Asia/Shanghai", next_run_at=datetime.now(timezone.utc))
            db.add_all([item, task]); await db.flush()
            scheduled = datetime.now(timezone.utc).replace(second=0, microsecond=0)
            first = await enqueue_run(db, task, "schedule", scheduled)
            await db.commit()
            second = await enqueue_run(db, task, "schedule", scheduled)
            self.assertEqual(first.id, second.id)
            self.assertEqual(first.status, "succeeded")
            self.assertEqual(int(await db.scalar(select(func.count(Report.id))) or 0), 1)
            self.assertEqual(first.output["matched"], 1)

    async def test_cost_and_confirmation_guards(self):
        async with self.sessions() as db:
            user = User(username="guards", email="guards@example.com", password_hash="x"); db.add(user); await db.flush()
            costly = AgentTask(user_id=user.id, name="Costly", task_type="keyword_monitor", config={}, schedule={"kind": "interval", "minutes": 5}, timezone="UTC", estimated_cost=2, cost_limit=1)
            risky = AgentTask(user_id=user.id, name="Webhook", task_type="keyword_monitor", config={}, schedule={"kind": "interval", "minutes": 5}, timezone="UTC", high_risk=True, confirmation_status="pending")
            db.add_all([costly, risky]); await db.flush()
            blocked = await enqueue_run(db, costly); waiting = await enqueue_run(db, risky)
            self.assertEqual(blocked.status, "blocked")
            self.assertEqual(waiting.status, "awaiting_confirmation")

    async def test_quiet_hours_delay_and_group_notifications(self):
        async with self.sessions() as db:
            user = User(username="quiet", email="quiet@example.com", password_hash="x"); db.add(user); await db.flush()
            current = datetime.now(timezone.utc).astimezone()
            preference = NotificationPreference(user_id=user.id, timezone="UTC", quiet_hours_enabled=True, quiet_start="00:00", quiet_end="23:59", digest_enabled=True)
            db.add(preference); await db.flush()
            first = await create_notification(db, user.id, "subscription", "Monitor", "First", group_key="monitor:1")
            second = await create_notification(db, user.id, "subscription", "Monitor", "Second", group_key="monitor:1")
            self.assertEqual(first.id, second.id)
            self.assertEqual(second.payload["group_count"], 2)
            self.assertIsNotNone(second.scheduled_delivery_at)

    def test_timezone_schedule_and_private_webhook_rejection(self):
        after = datetime(2026, 7, 28, 0, 30, tzinfo=timezone.utc)
        scheduled = next_run({"kind": "daily", "time": "09:00"}, "Asia/Shanghai", after)
        self.assertEqual(scheduled, datetime(2026, 7, 28, 1, 0, tzinfo=timezone.utc))
        with self.assertRaises(ValueError): validate_webhook_url("http://127.0.0.1/hook")
