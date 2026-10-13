"""Successful mutation responses must not race dependency-teardown commits."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.api.agent import create, detail, feedback, remove, update
from app.core.database import Base
from app.models.intelligence import AgentMessage
from app.models.user import User
from app.schemas.agent import ConversationCreate, ConversationUpdate, FeedbackCreate


class AgentTransactionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine("sqlite+aiosqlite:///" + str(Path(self.tmp.name) / "audit.db"))
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.sessions() as db:
            self.user = User(username="transaction", email="transaction@example.com", password_hash="x")
            db.add(self.user)
            await db.commit()

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.tmp.cleanup()

    async def test_create_update_feedback_delete_visible_before_dependency_exit(self):
        async with self.sessions() as writer:
            row = await create(ConversationCreate(title="committed"), self.user, writer)
            # Writer remains open: no get_db finalizer or test-side commit.
            async with self.sessions() as reader:
                self.assertEqual((await detail(row["id"], self.user, reader))["title"], "committed")
            await update(row["id"], ConversationUpdate(title="updated"), self.user, writer)
            async with self.sessions() as reader:
                self.assertEqual((await detail(row["id"], self.user, reader))["title"], "updated")
            message = AgentMessage(conversation_id=row["id"], role="assistant", content="fixture")
            writer.add(message)
            await writer.commit()
            await feedback(row["id"], message.id, FeedbackCreate(rating="up"), self.user, writer)
            from app.models.intelligence import MessageFeedback
            from sqlalchemy import select
            async with self.sessions() as reader:
                saved = await reader.scalar(select(MessageFeedback).where(MessageFeedback.message_id == message.id))
                self.assertEqual(saved.rating, "up")
            await remove(row["id"], self.user, writer)
            async with self.sessions() as reader:
                with self.assertRaises(HTTPException) as error:
                    await detail(row["id"], self.user, reader)
                self.assertEqual(error.exception.status_code, 404)

    async def test_commit_failure_cannot_return_success(self):
        async with self.sessions() as writer:
            with patch.object(writer, "commit", new_callable=AsyncMock, side_effect=RuntimeError("commit rejected")):
                with self.assertRaisesRegex(RuntimeError, "commit rejected"):
                    await create(ConversationCreate(title="not successful"), self.user, writer)
