import asyncio
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.core.database import Base
from app.models.orchestration import ToolDefinition
from app.models.platform import ConnectorDefinition, SubscriptionPlan
from app.models.user import User
from app.services.enterprise import provision_personal_tenant
from app.services.orchestration import seed_catalog as seed_tools
from app.services.platform import CONNECTORS, seed_catalog


class CatalogInitializationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine("sqlite+aiosqlite:///" + (Path(self.temp.name) / "catalog.db").as_posix())

        @event.listens_for(self.engine.sync_engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with self.sessions() as db:
            owner = User(username="catalog-owner", email="catalog@example.com", password_hash="test-only")
            db.add(owner)
            await db.flush()
            organization = await provision_personal_tenant(db, owner)
            self.org_id = organization.id
            await db.commit()

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.temp.cleanup()

    async def test_tools_initialize_connector_dependencies_with_foreign_keys(self):
        async with self.sessions() as db:
            await seed_tools(db, self.org_id)
            await db.commit()
            self.assertIsNotNone(await db.get(ConnectorDefinition, "slack"))
            self.assertEqual(await db.scalar(select(func.count()).select_from(ToolDefinition)), 3)

    async def test_concurrent_first_visits_are_idempotent_and_preserve_edits(self):
        async def initialize(index):
            async with self.sessions() as db:
                if index % 2:
                    await seed_tools(db, self.org_id)
                else:
                    await seed_catalog(db)
                await db.commit()

        await asyncio.gather(*(initialize(index) for index in range(12)))
        async with self.sessions() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(ConnectorDefinition)), len(CONNECTORS))
            self.assertEqual(await db.scalar(select(func.count()).select_from(SubscriptionPlan)), 3)
            self.assertEqual(await db.scalar(select(func.count()).select_from(ToolDefinition)), 3)
            connector = await db.get(ConnectorDefinition, "slack")
            connector.enabled = False
            await db.commit()
            await seed_tools(db, self.org_id)
            await db.refresh(connector)
            self.assertFalse(connector.enabled)
