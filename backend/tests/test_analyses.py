import unittest
from unittest.mock import patch
from datetime import datetime,timezone
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from app.core.database import Base
import app.models
from app.models.intelligence import ContentItem,DataSource,Event,EventContent
from app.models.user import User
from app.schemas.analyses import AnalysisRequest
from app.services.analysis_service import create_analysis,serialize
class AnalysisTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.engine=create_async_engine("sqlite+aiosqlite:///:memory:");
  async with self.engine.begin() as c: await c.run_sync(Base.metadata.create_all)
  self.sessions=async_sessionmaker(self.engine,expire_on_commit=False)
 async def asyncTearDown(self): await self.engine.dispose()
 async def test_no_evidence_refuses_conclusion(self):
  async with self.sessions() as db:
   u=User(username="a",email="a@a.com",password_hash="x");db.add(u);await db.flush()
   with self.assertRaises(HTTPException): await create_analysis(db,u.id,AnalysisRequest(analysis_type="summary"))
 async def test_claims_have_citations_and_versions_are_preserved(self):
  async with self.sessions() as db:
   u=User(username="b",email="b@b.com",password_hash="x");s=DataSource(key="real",name="Real",source_type="rss");db.add_all([u,s]);await db.flush()
   c=ContentItem(source_id=s.id,external_id="1",canonical_url="https://example.com/1",title="Verified release",body="Official release evidence",content_type="article",content_hash="b"*64,published_at=datetime.now(timezone.utc));e=Event(title="Release",slug="release",last_activity_at=datetime.now(timezone.utc));db.add_all([c,e]);await db.flush();db.add(EventContent(event_id=e.id,content_item_id=c.id));await db.flush()
   req=AnalysisRequest(analysis_type="forecast",event_ids=[e.id])
   with patch("app.services.analysis_service.llm_is_configured", return_value=False):
    first=await create_analysis(db,u.id,req);second=await create_analysis(db,u.id,req,first)
   data=await serialize(db,first);self.assertEqual(data["evidence_coverage"],100);self.assertTrue(data["citations"]);self.assertTrue(data["result"]["claims"][0]["inference"]);self.assertEqual(second.version,2);self.assertNotEqual(first.id,second.id)
