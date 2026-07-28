import unittest
from datetime import datetime,timedelta,timezone
from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from app.core.database import Base
import app.models
from app.models.user import User
from app.models.intelligence import AlertIncident,AlertRule,BIQueryHistory,ContentItem,DataSource,Event,EventContent
from app.services.alerts import act,replay,scan_rule
from app.services.controlled_bi import DIMENSIONS,METRICS,execute,plan
class Stage10Tests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.engine=create_async_engine("sqlite+aiosqlite:///:memory:");
  async with self.engine.begin() as c:await c.run_sync(Base.metadata.create_all)
  self.sessions=async_sessionmaker(self.engine,expire_on_commit=False)
 async def asyncTearDown(self):await self.engine.dispose()
 async def seed(self,db):
  u=User(username="alerts",email="alerts@test.local",password_hash="x");s=DataSource(key="official-test",name="Official",source_type="rss");db.add_all([u,s]);await db.flush();now=datetime.now(timezone.utc);c=ContentItem(source_id=s.id,external_id="1",canonical_url="https://example.test/1",title="OpenAI security incident",body="Critical Agent risk disclosure",content_type="article",content_hash="a"*64,published_at=now,sentiment="negative",is_official=True);e=Event(title="OpenAI incident",slug="alert-event",heat_score=88,risk_score=76,last_activity_at=now);db.add_all([c,e]);await db.flush();db.add(EventContent(event_id=e.id,content_item_id=c.id));await db.flush();return u,e
 async def test_composite_rule_triggers_once_with_real_evidence(self):
  async with self.sessions() as db:
   u,e=await self.seed(db);r=AlertRule(user_id=u.id,name="Critical",rule_type="composite",config={"conditions":[{"type":"keyword","keywords":["OpenAI"]},{"type":"ai_risk","min":70},{"type":"official","min_count":1}]},combinator="all",severity="critical");db.add(r);await db.flush();first=await scan_rule(db,r);second=await scan_rule(db,r);self.assertEqual(len(first),1);self.assertEqual(len(second),1);self.assertEqual(int(await db.scalar(select(func.count()).select_from(AlertIncident))),1);incident=await db.scalar(select(AlertIncident));self.assertTrue(incident.evidence)
 async def test_replay_has_no_incident_side_effect(self):
  async with self.sessions() as db:
   u,e=await self.seed(db);r=AlertRule(user_id=u.id,name="Heat",rule_type="heat",config={"min":80});db.add(r);await db.flush();run=await replay(db,r,u.id,datetime.now(timezone.utc)-timedelta(days=1),datetime.now(timezone.utc)+timedelta(days=1));self.assertEqual(run.matched_count,1);self.assertEqual(int(await db.scalar(select(func.count()).select_from(AlertIncident))),0)
 async def test_incident_lifecycle_and_false_positive(self):
  async with self.sessions() as db:
   u,e=await self.seed(db);r=AlertRule(user_id=u.id,name="Risk",rule_type="ai_risk",config={"min":70});db.add(r);await db.flush();await scan_rule(db,r);x=await db.scalar(select(AlertIncident));await act(db,x,u.id,"acknowledge",None,"reviewed");self.assertEqual(x.status,"acknowledged");await act(db,x,u.id,"false_positive",None,"known test");self.assertEqual(x.status,"closed");self.assertTrue(x.is_false_positive)
 async def test_controlled_bi_uses_whitelist_even_for_sql_text(self):
  async with self.sessions() as db:
   u,e=await self.seed(db);question="DROP TABLE users; 最近7天按来源统计内容";p=plan(question);self.assertIn(p["metric"],METRICS);self.assertIn(p["dimension"],DIMENSIONS);self.assertNotIn("sql",p);history,result=await execute(db,u.id,question);self.assertEqual(history.question,question);self.assertIn("definition",result["metric"]);self.assertIn("from",result["range"]);self.assertEqual(int(await db.scalar(select(func.count()).select_from(BIQueryHistory))),1)
