"""Production regression across global decision intelligence and action execution."""
import unittest
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
import app.models
from app.core.database import Base
from app.models.action_loop import ResponseAction
from app.models.global_intelligence import DecisionOption,DecisionRoom,Scenario
from app.models.intelligence import Event
from app.models.user import User
from app.services.action_loop import create_run
from app.services.enterprise import provision_personal_tenant

class DecisionToActionE2E(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.engine=create_async_engine("sqlite+aiosqlite:///:memory:");self.sessions=async_sessionmaker(self.engine,expire_on_commit=False)
  async with self.engine.begin() as c:await c.run_sync(Base.metadata.create_all)
 async def asyncTearDown(self):await self.engine.dispose()
 async def test_decision_option_becomes_approved_idempotent_action(self):
  async with self.sessions() as db:
   user=User(username="decision-e2e",email="decision-e2e@example.com",password_hash="x");db.add(user);await db.flush();org=await provision_personal_tenant(db,user);event=Event(title="Cross-region policy",slug="cross-region-policy");db.add(event);await db.flush()
   scenario=Scenario(organization_id=org.id,event_id=event.id,name="Response window",assumptions=["Evidence remains valid"],impact_chain=[],evidence_content_ids=[],created_by=user.id);db.add(scenario);await db.flush();room=DecisionRoom(organization_id=org.id,event_id=event.id,name="Response room",status="frozen",created_by=user.id);db.add(room);await db.flush();option=DecisionOption(organization_id=org.id,room_id=room.id,title="Notify stakeholders",status="selected",evidence_content_ids=[],created_by=user.id);db.add(option);await db.flush()
   action=ResponseAction(organization_id=org.id,event_id=event.id,scenario_id=scenario.id,decision_room_id=room.id,title=option.title,owner_id=user.id,created_by=user.id,status="approved",risk_level="medium",budget_cents=1000,spent_cents=0,evidence_content_ids=[]);db.add(action);await db.flush();first,created=await create_run(db,action,"decision-to-action-001");second,created_again=await create_run(db,action,"decision-to-action-001")
   self.assertTrue(created);self.assertFalse(created_again);self.assertEqual(first.id,second.id);self.assertEqual(action.status,"executing");self.assertEqual(action.decision_room_id,room.id)
if __name__=="__main__":unittest.main()
