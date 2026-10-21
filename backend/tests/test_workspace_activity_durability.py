"""Writes must be visible to a fresh reader before a handler returns."""
import tempfile
import unittest
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
import app.models
from app.api import reports
from app.api.personalization import record_view
from app.core.database import Base
from app.models.intelligence import Report
from app.models.user import User
from app.schemas.personalization import RecentViewRequest
from app.schemas.reports import ReportCreate, ReportUpdate, VersionCreate
from app.services.stage3 import workspace_data


class ActivityDurabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_report_create_rename_version_restore_delete_and_view_are_durable(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_async_engine(f"sqlite+aiosqlite:///{Path(directory).as_posix()}/durability.db")
            try:
                async with engine.begin() as connection:
                    await connection.run_sync(Base.metadata.create_all)
                sessions = async_sessionmaker(engine, expire_on_commit=False)
                async with sessions() as writer:
                    user = User(username='writer', email='writer@example.com', password_hash='x')
                    writer.add(user); await writer.commit()
                    created = await reports.create(ReportCreate(title='Original', report_type='daily'), user, writer)
                    rid, first_version = created['id'], created['version_id']

                    async def workspace():
                        async with sessions() as reader:
                            return await workspace_data(reader, user.id)

                    self.assertEqual((await workspace())['recent_reports'][0]['title'], 'Original')
                    await reports.update(rid, ReportUpdate(title='Renamed'), user, writer)
                    self.assertEqual((await workspace())['recent_reports'][0]['title'], 'Renamed')
                    await record_view(RecentViewRequest(target_type='report', target_id=rid, title='Wrong'), user, writer)
                    self.assertEqual((await workspace())['recent_views'][0]['title'], 'Renamed')
                    version = await reports.save(rid, VersionCreate(content_markdown='# Saved'), user, writer)
                    async with sessions() as reader:
                        saved = await reports.detail(rid, user, reader)
                        self.assertEqual(saved['current_version']['id'], version['id'])
                    # Force an old time to prove restore explicitly marks the report as updated.
                    from datetime import datetime, timezone
                    report = await writer.get(Report, rid)
                    report.updated_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
                    await writer.commit()
                    await reports.restore(rid, first_version, user, writer)
                    async with sessions() as reader:
                        restored = await reports.detail(rid, user, reader)
                        self.assertEqual(restored['current_version']['id'], first_version)
                        row = await reader.get(Report, rid)
                        self.assertGreater(row.updated_at.year, 2000)
                    await reports.remove(rid, user, writer)
                    result = await workspace()
                    self.assertEqual(result['recent_reports'], [])
                    self.assertFalse(result['recent_views'][0]['available'])
            finally:
                await engine.dispose()
