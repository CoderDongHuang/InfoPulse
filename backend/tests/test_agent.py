import unittest
from unittest.mock import patch
from datetime import datetime,timezone
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from app.core.database import Base
import app.models
from app.models.intelligence import ContentItem,Conversation,DataSource,Event,EventContent
from app.models.user import User
from app.services.agent_service import answer,gather
class AgentTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.engine=create_async_engine("sqlite+aiosqlite:///:memory:")
  async with self.engine.begin() as c:await c.run_sync(Base.metadata.create_all)
  self.sessions=async_sessionmaker(self.engine,expire_on_commit=False)
 async def asyncTearDown(self):await self.engine.dispose()
 async def test_fixed_event_gathers_real_evidence_and_cited_answer(self):
  async with self.sessions() as db:
   u=User(username="agent",email="agent@example.com",password_hash="x");s=DataSource(key="real-agent",name="Real source",source_type="rss");db.add_all([u,s]);await db.flush();x=ContentItem(source_id=s.id,external_id="1",canonical_url="https://example.com/agent",title="OpenAI agent release",body="Official evidence",content_type="article",content_hash="c"*64,published_at=datetime.now(timezone.utc));e=Event(title="Agent release",slug="agent-release",last_activity_at=datetime.now(timezone.utc));db.add_all([x,e]);await db.flush();db.add(EventContent(event_id=e.id,content_item_id=x.id));c=Conversation(user_id=u.id,event_id=e.id);db.add(c);await db.flush();rows,tools=await gather(db,u.id,c,"总结事件",[])
   with patch("app.services.agent_service.llm_is_configured",return_value=False):result,model=await answer("总结事件",rows)
   self.assertEqual(len(rows),1);self.assertEqual(tools[0][0],"read_event");self.assertTrue(result["claims"][0]["citation_indexes"]);self.assertEqual(model,"evidence-rules-v1")
 async def test_no_evidence_returns_refusal_not_fabrication(self):
  result,_=await answer("未知事实",[]);self.assertEqual(result["claims"],[]);self.assertIn("没有足够",result["answer"])
