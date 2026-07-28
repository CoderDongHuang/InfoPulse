import unittest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
import app.models
from app.core.database import Base
from app.models.user import User
from app.schemas.operations import ProductEventCreate,FeedbackCreate,ReleaseCreate
from app.api.operations_center import track,feedback,analytics,create_release,releases

class OperationsCenterTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.engine=create_async_engine("sqlite+aiosqlite:///:memory:");self.sessions=async_sessionmaker(self.engine,expire_on_commit=False)
  async with self.engine.begin() as connection:await connection.run_sync(Base.metadata.create_all)
 async def asyncTearDown(self):await self.engine.dispose()
 async def test_controlled_analytics_feedback_and_release_records(self):
  async with self.sessions() as db:
   admin=User(username="ops",email="ops@example.com",password_hash="x",is_admin=True);db.add(admin);await db.flush()
   await track(ProductEventCreate(event_name="help_opened",route="/help",properties={"source":"navigation"}),admin,db)
   row=await feedback(FeedbackCreate(category="idea",rating=5,message="Add a clearer source status"),admin,db);self.assertEqual(row["status"],"new")
   created=await create_release(ReleaseCreate(version="1.2.0",environment="staging",status="succeeded",commit_sha="abcdef1",notes="QA passed"),admin,db);self.assertEqual(created["version"],"1.2.0")
   await db.commit();summary=await analytics(30,admin,db);self.assertEqual(summary["events"]["help_opened"],1);self.assertEqual(summary["average_rating"],5.0);self.assertEqual((await releases(admin,db))[0]["commit_sha"],"abcdef1")
 async def test_feedback_rejects_secret_shapes(self):
  async with self.sessions() as db:
   user=User(username="member",email="member@example.com",password_hash="x");db.add(user);await db.flush()
   with self.assertRaises(HTTPException) as raised:await feedback(FeedbackCreate(category="bug",rating=2,message="token=do-not-store-this"),user,db)
   self.assertEqual(raised.exception.status_code,422)
