import unittest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
import app.models
from app.core.database import Base
from app.models.autonomous_enterprise import PrivacyBudget
from app.models.commercialization import ApprovalFlow
from app.models.user import User
from app.schemas.autonomous_enterprise import ApprovalDecision,ApprovalRunCreate,PrivacyQuery
from app.services.autonomous_enterprise import causal_effect,decide_node,forecast_cost,simulate_policy,spend_privacy,start_approval
from app.services.enterprise import provision_personal_tenant
class AutonomousEnterpriseTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.engine=create_async_engine("sqlite+aiosqlite:///:memory:");self.sessions=async_sessionmaker(self.engine,expire_on_commit=False)
  async with self.engine.begin() as c:await c.run_sync(Base.metadata.create_all)
 async def asyncTearDown(self):await self.engine.dispose()
 async def seed(self,db):
  u=User(username="autonomy",email="autonomy@example.com",password_hash="x");db.add(u);await db.flush();o=await provision_personal_tenant(db,u);await db.flush();return u,o
 async def test_approval_runtime_is_idempotent_signed_and_compensating(self):
  async with self.sessions() as db:
   u,o=await self.seed(db);f=ApprovalFlow(organization_id=o.id,name="High risk",trigger="high",graph={"nodes":[{"id":"legal","type":"approval"}],"edges":[]},created_by=u.id);db.add(f);await db.flush();p=ApprovalRunCreate(flow_id=f.id,subject_type="action",subject_id="a1",idempotency_key="approval-0001");a=await start_approval(db,o.id,u.id,p);b=await start_approval(db,o.id,u.id,p);self.assertEqual(a.id,b.id);a=await decide_node(db,o.id,u.id,a.id,ApprovalDecision(node_id="legal",decision="rejected",signature_nonce="nonce-0001"));self.assertEqual(a.status,"compensating");self.assertEqual(len(a.signature_chain),1);self.assertEqual(a.compensation_log[0]["status"],"scheduled")
 async def test_privacy_budget_is_consumed_and_blocks_attacks(self):
  async with self.sessions() as db:
   u,o=await self.seed(db);b=PrivacyBudget(organization_id=o.id,dataset_key="benchmark",period="2026-08",epsilon_limit=1,epsilon_used=0,minimum_cohort=10);db.add(b);await db.flush();audit=await spend_privacy(db,o.id,u.id,PrivacyQuery(dataset_key="benchmark",query={"metric":"sla"},epsilon_cost=.2,cohort_size=30));self.assertEqual(audit.status,"approved");self.assertAlmostEqual(b.epsilon_used,.2)
   with self.assertRaises(HTTPException) as raised:await spend_privacy(db,o.id,u.id,PrivacyQuery(dataset_key="benchmark",query={"metric":"sla","slice":"tiny"},epsilon_cost=.1,cohort_size=4,similar_query_count=9))
   self.assertEqual(raised.exception.status_code,429)
 def test_policy_causal_and_finops_controls(self):
  good=simulate_policy({"match":{"risk":"high"}},[{"input":{"risk":"high"},"allow":True},{"input":{"risk":"low"},"allow":False}]);self.assertTrue(good["ready"])
  bad=simulate_policy({"match":{"risk":"high"}},[{"input":{"risk":"low"},"allow":True}]);self.assertFalse(bad["ready"])
  self.assertEqual(causal_effect({"before":10,"after":18},{"before":10,"after":12}),6);self.assertEqual(forecast_cost([100,100,500])["anomaly"],False)
if __name__=="__main__":unittest.main()
