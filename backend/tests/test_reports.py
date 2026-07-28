import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.api.reports import create, detail, restore, save, templates
from app.core.database import Base
from app.models.intelligence import ContentItem, DataSource
from app.models.user import User
from app.schemas.reports import ReportCreate, VersionCreate
from app.services.report_export import export_report


class ReportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_templates_and_immutable_versions(self):
        async with self.sessions() as db:
            user = User(username="reporter", email="reporter@example.com", password_hash="x")
            source = DataSource(key="report-source", name="Official", source_type="rss")
            db.add_all([user, source])
            await db.flush()
            item = ContentItem(source_id=source.id, external_id="r1", canonical_url="https://example.com/r1", title="Verified fact", body="Primary evidence", content_type="article", content_hash="d" * 64, published_at=datetime.now(timezone.utc))
            db.add(item)
            await db.flush()

            self.assertEqual(len(await templates(user)), 6)
            created = await create(ReportCreate(title="Daily brief", report_type="daily", source_config={"content_ids": [item.id]}), user, db)
            first = await detail(created["id"], user, db)
            second = await save(created["id"], VersionCreate(content_markdown="# Updated", citation_content_ids=[item.id]), user, db)
            self.assertEqual(second["version_number"], 2)
            await restore(created["id"], first["current_version"]["id"], user, db)
            restored = await detail(created["id"], user, db)
            self.assertEqual(restored["current_version"]["version_number"], 1)

    async def test_ownership_and_invalid_citations_are_rejected(self):
        async with self.sessions() as db:
            owner = User(username="owner", email="owner@example.com", password_hash="x")
            other = User(username="other", email="other@example.com", password_hash="x")
            db.add_all([owner, other])
            await db.flush()
            created = await create(ReportCreate(title="Private", report_type="risk"), owner, db)
            with self.assertRaises(HTTPException) as ownership:
                await detail(created["id"], other, db)
            self.assertEqual(ownership.exception.status_code, 404)
            with self.assertRaises(HTTPException) as citation:
                await save(created["id"], VersionCreate(content_markdown="Unsupported claim", citation_content_ids=["not-accessible"]), owner, db)
            self.assertEqual(citation.exception.status_code, 403)

    async def test_markdown_and_html_exports_keep_references(self):
        class Object:
            pass
        report, version = Object(), Object()
        report.id, report.title, report.report_type = "report", "行业简报", "industry"
        version.id, version.version_number = "version", 3
        version.content_markdown, version.structured_content = "# 发现\n已核实事实 [1]", {"charts": []}
        citation = {"title": "原始来源", "url": "https://example.com/source"}
        with tempfile.TemporaryDirectory() as directory, patch("app.services.report_export.ROOT", Path(directory)):
            markdown = export_report(report, version, [citation], "markdown")
            html = export_report(report, version, [citation], "html")
            self.assertIn("https://example.com/source", markdown.read_text(encoding="utf-8"))
            self.assertIn("https://example.com/source", html.read_text(encoding="utf-8"))
