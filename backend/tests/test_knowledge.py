import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from app.core.database import Base
import app.models
from app.models.user import User
from app.models.intelligence import KnowledgeBase,KnowledgeDocument
from app.services.knowledge import delete_document,process_document,search,validate_public_url,validate_upload,storage

class KnowledgeTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.engine=create_async_engine("sqlite+aiosqlite:///:memory:")
  async with self.engine.begin() as c:await c.run_sync(Base.metadata.create_all)
  self.sessions=async_sessionmaker(self.engine,expire_on_commit=False)
  self.tmp=tempfile.TemporaryDirectory();self.old=storage.local;storage.local=Path(self.tmp.name)
 async def asyncTearDown(self):storage.local=self.old;self.tmp.cleanup();await self.engine.dispose()
 async def seed(self,db,text="OpenAI released a secure Agent SDK"):
  u1=User(username="owner",email="owner@x.test",password_hash="x");u2=User(username="other",email="other@x.test",password_hash="x");db.add_all([u1,u2]);await db.flush();base=KnowledgeBase(user_id=u1.id,name="Private research");db.add(base);await db.flush();doc=KnowledgeDocument(knowledge_base_id=base.id,user_id=u1.id,filename="notes.md",source_type="upload",mime_type="text/markdown",byte_size=len(text));db.add(doc);await db.flush();await process_document(db,doc,text.encode());return u1,u2,base,doc
 async def test_hybrid_search_is_owned_and_located(self):
  async with self.sessions() as db:
   owner,other,base,doc=await self.seed(db)
   result=await search(db,owner.id,[base.id],"OpenAI Agent",5);self.assertEqual(result[0]["citation_type"],"private");self.assertEqual(result[0]["paragraph"],1)
   self.assertEqual(await search(db,other.id,[base.id],"OpenAI",5),[])
 async def test_deleted_document_cannot_be_recalled(self):
  async with self.sessions() as db:
   owner,_,base,doc=await self.seed(db);self.assertTrue(await search(db,owner.id,[base.id],"secure",5));await delete_document(db,doc);self.assertEqual(await search(db,owner.id,[base.id],"secure",5),[])
 async def test_reindex_creates_version_and_keeps_active_filter(self):
  async with self.sessions() as db:
   owner,_,base,doc=await self.seed(db);first=doc.active_version_id;await process_document(db,doc);self.assertNotEqual(first,doc.active_version_id);result=await search(db,owner.id,[base.id],"Agent",10);self.assertTrue(result);self.assertEqual(len({x["chunk_id"] for x in result}),len(result))
 def test_upload_security_rejects_spoofed_and_binary_text(self):
  with self.assertRaises(ValueError):validate_upload("fake.pdf",b"not a pdf")
  with self.assertRaises(ValueError):validate_upload("bad.txt",b"a\x00b")
 async def test_ssrf_rejects_loopback(self):
  with patch("socket.getaddrinfo",return_value=[(2,1,6,"",("127.0.0.1",80))]):
   with self.assertRaises(ValueError):await validate_public_url("http://example.test/private")
