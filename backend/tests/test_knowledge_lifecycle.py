"""Regression coverage for durable upload staging and explicit retry state."""
import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, UploadFile

from app.api.knowledge import reindex, upload, web_import
from app.schemas.knowledge import WebImportCreate
from app.services.knowledge import Storage
from scripts.init_local import initialize
from tests import test_knowledge


class KnowledgeLifecycleTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_knowledge.KnowledgeTests.asyncSetUp
    asyncTearDown = test_knowledge.KnowledgeTests.asyncTearDown
    seed = test_knowledge.KnowledgeTests.seed
    async def test_upload_is_staged_before_database_commit(self):
        async with self.sessions() as db:
            owner, _, base, _ = await self.seed(db)
            commit = db.commit
            staged = []

            async def stage(identifier, data):
                storage = Storage()
                storage.local = Path(self.tmp.name)
                storage.put("staging/" + identifier, data)
                staged.append(identifier)

            async def checked_commit():
                self.assertTrue(staged)
                self.assertEqual((Path(self.tmp.name) / "staging" / staged[-1]).read_bytes(), b"durable content")
                await commit()

            with patch("app.api.knowledge.enqueue_document", side_effect=stage), patch.object(db, "commit", side_effect=checked_commit):
                result = await upload(base.id, [UploadFile(io.BytesIO(b"durable content"), filename="upload.md")], owner, db)
            self.assertEqual(result[0]["status"], "queued")
            self.assertEqual(result[0]["id"], staged[0])

    async def test_web_import_staging_failure_does_not_commit_document(self):
        async with self.sessions() as db:
            owner, _, base, _ = await self.seed(db)
            with patch("app.api.knowledge.fetch_web", return_value=("page.md", b"content")), patch("app.api.knowledge.enqueue_document", side_effect=OSError("disk full")), patch.object(db, "commit", new_callable=AsyncMock) as commit:
                with self.assertRaises(OSError):
                    await web_import(base.id, WebImportCreate(url="https://example.com/page"), owner, db)
                commit.assert_not_awaited()
            await db.rollback()

    async def test_reindex_resets_exhausted_attempts_and_rejects_active_job(self):
        async with self.sessions() as db:
            owner, _, _, doc = await self.seed(db)
            doc.status = "failed"
            doc.processing_attempts = 3
            doc.lease_until = datetime.now(timezone.utc)
            doc.error_message = "old failure"
            await db.commit()
            with patch("app.api.knowledge.enqueue_document", new_callable=AsyncMock) as enqueue:
                result = await reindex(doc.id, owner, db)
                enqueue.assert_awaited_once_with(doc.id)
                self.assertEqual(result["status"], "queued")
                self.assertEqual(doc.processing_attempts, 0)
                self.assertIsNone(doc.lease_until)
                self.assertEqual(doc.error_message, "")
                with self.assertRaises(HTTPException) as raised:
                    await reindex(doc.id, owner, db)
                self.assertEqual(raised.exception.status_code, 409)
                self.assertEqual(enqueue.await_count, 1)

    async def test_upload_read_is_bounded_before_validation(self):
        async with self.sessions() as db:
            owner, _, base, _ = await self.seed(db)
            file = AsyncMock()
            file.filename = "large.txt"
            file.read.return_value = b"too large"
            with patch("app.api.knowledge.settings.KNOWLEDGE_MAX_FILE_MB", 0):
                with self.assertRaises(HTTPException):
                    await upload(base.id, [file], owner, db)
            file.read.assert_awaited_once_with(1)


class InitializationTests(unittest.TestCase):
    def test_unique_secrets_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first.env", Path(directory) / "second.env"
            initialize(first)
            initialize(second)
            a, b = first.read_text(encoding="utf-8"), second.read_text(encoding="utf-8")
            self.assertIn("DATABASE_URL=sqlite+aiosqlite:///./infopulse.db", a)
            self.assertNotEqual(a, b)
            self.assertNotIn("JWT_SECRET_KEY=change-me", a)
            self.assertIn("LLM_API_KEY=\n", a)
            self.assertIn("CRAWLER_ENABLED=false", a)
            self.assertIn("MEDIA_WORKER_ENABLED=false", a)
            with self.assertRaises(FileExistsError):
                initialize(first)
            self.assertEqual(first.read_text(encoding="utf-8"), a)
