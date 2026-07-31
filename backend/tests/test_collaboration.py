import unittest
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
import app.models
from app.core.database import Base
from app.models.multimodal import CollaborativeDocument
from app.models.user import User
from app.schemas.multimodal import ChangeCreate
from app.services.collaboration import apply_change,digest
from app.services.enterprise import provision_personal_tenant

class CollaborationTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.engine=create_async_engine("sqlite+aiosqlite:///:memory:");self.sessions=async_sessionmaker(self.engine,expire_on_commit=False)
  async with self.engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
 async def asyncTearDown(self):await self.engine.dispose()
 async def setup_doc(self,db):
  user=User(username="collabowner",email="collab@test.local",password_hash="x");db.add(user);await db.flush();org=await provision_personal_tenant(db,user);snapshot={"title":"Brief","structured_content":{"risk":"low"}};doc=CollaborativeDocument(organization_id=org.id,resource_type="workflow",resource_id="resource-1",snapshot=snapshot,snapshot_hash=digest(snapshot),updated_by=user.id);db.add(doc);await db.flush();return user,doc
 async def test_idempotency_non_overlapping_merge_and_conflict(self):
  async with self.sessions() as db:
   user,doc=await self.setup_doc(db)
   first=ChangeCreate(base_version=1,client_id="browser-a",client_sequence=1,operations=[{"op":"set","path":"/title","value":"Updated"}]);row=await apply_change(db,doc,user.id,first);same=await apply_change(db,doc,user.id,first);self.assertEqual(row.id,same.id);self.assertEqual(doc.version,2)
   merged=await apply_change(db,doc,user.id,ChangeCreate(base_version=1,client_id="browser-b",client_sequence=1,operations=[{"op":"set","path":"/structured_content/risk","value":"high"}]));self.assertEqual(merged.status,"applied");self.assertEqual(doc.version,3)
   conflict=await apply_change(db,doc,user.id,ChangeCreate(base_version=1,client_id="browser-c",client_sequence=1,operations=[{"op":"set","path":"/title","value":"Other"}]));self.assertEqual(conflict.status,"conflict");self.assertIn("server_snapshot",conflict.conflict)
 def test_rejects_prototype_pollution_paths(self):
  with self.assertRaises(ValueError):ChangeCreate(base_version=1,client_id="browser-x",client_sequence=1,operations=[{"op":"set","path":"/__proto__/admin","value":True}])

if __name__=="__main__":unittest.main()
