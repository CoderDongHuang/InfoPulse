import unittest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
import app.models
from app.core.database import Base
from app.models.global_intelligence import DecisionOption,DecisionRoom
from app.models.intelligence import ContentItem,DataSource,Event,EventContent
from app.models.user import User
from app.schemas.global_intelligence import ScenarioCreate
from app.services.enterprise import provision_personal_tenant
from app.services.global_intelligence import build_narratives,scenario

class GlobalIntelligenceTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.engine=create_async_engine("sqlite+aiosqlite:///:memory:");self.sessions=async_sessionmaker(self.engine,expire_on_commit=False)
  async with self.engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
 async def asyncTearDown(self):await self.engine.dispose()
 async def seed(self,db):
  user=User(username="globalowner",email="globalowner@example.com",password_hash="x");db.add(user);await db.flush();org=await provision_personal_tenant(db,user);source=DataSource(key="global-source",name="Global source",source_type="rss");db.add(source);event=Event(title="Policy event",slug="policy-event");db.add_all([source,event]);await db.flush()
  a=ContentItem(source_id=source.id,external_id="en",canonical_url="https://example.com/en",title="OpenAI policy update",body="Unconfirmed rumor",content_type="article",language="en",region="US",content_hash="a"*64,entities=["openai","policy"]);b=ContentItem(source_id=source.id,external_id="zh",canonical_url="https://example.com/zh",title="OpenAI 政策更新",body="网传消息",content_type="article",language="zh",region="CN",content_hash="b"*64,entities=["openai","policy"]);db.add_all([a,b]);await db.flush();db.add_all([EventContent(event_id=event.id,content_item_id=a.id),EventContent(event_id=event.id,content_item_id=b.id)]);await db.flush();return user,org,event,a,b
 async def test_narrative_requires_cross_language_evidence_and_signals_are_review_only(self):
  async with self.sessions() as db:
   _user,org,event,_a,_b=await self.seed(db);rows=await build_narratives(db,org.id,event.id);self.assertEqual(len(rows),1);self.assertEqual(rows[0].languages,["en","zh"])
 async def test_scenario_keeps_evidence_and_marks_missing_regional_context(self):
  async with self.sessions() as db:
   user,org,event,a,b=await self.seed(db);x=await scenario(db,org.id,user.id,ScenarioCreate(event_id=event.id,name="Policy impact",assumptions=["Official position remains unchanged"],evidence_content_ids=[a.id,b.id]));self.assertEqual(set(x.evidence_content_ids),{a.id,b.id});self.assertEqual(x.impact_chain[-1]["status"],"not_a_prediction")
 async def test_decision_room_option_data_is_evidence_bound(self):
  async with self.sessions() as db:
   user,org,event,a,_b=await self.seed(db);room=DecisionRoom(organization_id=org.id,event_id=event.id,name="Response",created_by=user.id);db.add(room);await db.flush();opt=DecisionOption(organization_id=org.id,room_id=room.id,title="Monitor",evidence_content_ids=[a.id],created_by=user.id);db.add(opt);await db.flush();self.assertEqual((await db.get(DecisionOption,opt.id)).evidence_content_ids,[a.id])

if __name__=="__main__":unittest.main()
