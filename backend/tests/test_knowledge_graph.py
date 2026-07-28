import unittest
from datetime import datetime,timedelta,timezone
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from app.core.database import Base
import app.models
from app.models.intelligence import ContentItem,DataSource,EntityAlias,Event,EventContent
from app.services.knowledge_graph import build_entities,build_propagation,quality,resolve_entity

class KnowledgeGraphTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.engine=create_async_engine("sqlite+aiosqlite:///:memory:")
  async with self.engine.begin() as c:await c.run_sync(Base.metadata.create_all)
  self.sessions=async_sessionmaker(self.engine,expire_on_commit=False)
 async def asyncTearDown(self):await self.engine.dispose()
 async def seed(self,db,cross=True,refer=True):
  a=DataSource(key="github-graph",name="GitHub",source_type="api");b=DataSource(key="news-graph",name="News",source_type="rss");db.add_all([a,b]);await db.flush();now=datetime.now(timezone.utc);first=ContentItem(source_id=a.id,external_id="first",canonical_url="https://github.com/openai/sdk",title="OpenAI launches Agent SDK for developers",body="OpenAI and Microsoft announced the Agent SDK project.",content_type="article",content_hash="a"*64,published_at=now);second=ContentItem(source_id=b.id if cross else a.id,external_id="second",canonical_url="https://news.test/story",title="Industry response",body=("Report cites https://github.com/openai/sdk and discusses OpenAI Agent SDK." if refer else "A separate industry article with no citation."),content_type="article",content_hash="b"*64,published_at=now+timedelta(hours=1),view_count=100);event=Event(title="Agent SDK",slug=f"agent-sdk-{cross}-{refer}",last_activity_at=now);db.add_all([first,second,event]);await db.flush();db.add_all([EventContent(event_id=event.id,content_item_id=first.id),EventContent(event_id=event.id,content_item_id=second.id)]);await db.flush();return event
 async def test_entities_are_normalized_with_evidence(self):
  async with self.sessions() as db:
   event=await self.seed(db);rows=await build_entities(db,event.id);names={x.name for x,_ in rows};self.assertIn("OpenAI",names);self.assertTrue(all(link.evidence_content_ids for _,link in rows));openai=next(x for x,_ in rows if x.name=="OpenAI");db.add(EntityAlias(entity_id=openai.id,alias="开放人工智能",normalized_alias="开放人工智能",language="zh"));await db.flush();self.assertEqual((await resolve_entity(db,"开放人工智能","company")).id,openai.id)
 async def test_cross_platform_explicit_reference_builds_evidenced_edge(self):
  async with self.sessions() as db:
   event=await self.seed(db);nodes,edges,status=await build_propagation(db,event.id);self.assertEqual(status,"ready");self.assertEqual(len(edges),1);self.assertEqual(edges[0].relation_type,"reference");self.assertTrue(edges[0].evidence_content_id);self.assertIn("github.com",edges[0].evidence_quote)
 async def test_no_cross_platform_or_reference_refuses_path(self):
  async with self.sessions() as db:
   event=await self.seed(db,cross=True,refer=False);_,edges,status=await build_propagation(db,event.id);self.assertEqual(edges,[]);self.assertEqual(status,"insufficient_evidence")
  async with self.sessions() as db:
   event=await self.seed(db,cross=False,refer=True);_,edges,status=await build_propagation(db,event.id);self.assertEqual(edges,[]);self.assertEqual(status,"insufficient_evidence")
 async def test_quality_uses_real_graph_records(self):
  async with self.sessions() as db:
   event=await self.seed(db);await build_entities(db,event.id);await build_propagation(db,event.id);snapshot=await quality(db,event.id);self.assertEqual(snapshot.evidence_coverage,1);self.assertEqual(snapshot.verified_ratio,1);self.assertGreater(snapshot.entity_precision,0)
