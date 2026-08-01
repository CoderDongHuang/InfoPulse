import unittest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
import app.models
from app.core.database import Base
from app.models.trusted_ecosystem import DataContract,FederationAgreement,IntelligenceProduct,MarketplaceOrder
from app.models.user import User
from app.schemas.trusted_ecosystem import EnvelopeCreate,OrderTransition,ResponsibilityCreate
from app.services.enterprise import provision_personal_tenant
from app.services.trusted_ecosystem import append_responsibility,create_envelope,secure_aggregate,transition_order,trust_score,withdraw_contract
class TrustedEcosystemTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.engine=create_async_engine("sqlite+aiosqlite:///:memory:");self.sessions=async_sessionmaker(self.engine,expire_on_commit=False)
  async with self.engine.begin() as c:await c.run_sync(Base.metadata.create_all)
 async def asyncTearDown(self):await self.engine.dispose()
 async def seed(self,db):
  a=User(username="federation-a",email="fa@example.com",password_hash="x");b=User(username="federation-b",email="fb@example.com",password_hash="x");db.add_all([a,b]);await db.flush();oa=await provision_personal_tenant(db,a);ob=await provision_personal_tenant(db,b);await db.flush();return a,b,oa,ob
 async def test_federated_exchange_is_sanitized_and_withdrawal_propagates(self):
  async with self.sessions() as db:
   a,_b,oa,ob=await self.seed(db);contract=DataContract(organization_id=oa.id,dataset_key="sla",purpose="benchmark",allowed_uses=["aggregate"],regions=["global"],created_by=a.id);agreement=FederationAgreement(organization_id=oa.id,partner_organization_id=ob.id,purpose="benchmark",allowed_metrics=["sla_minutes"],minimum_cohort=10,created_by=a.id);db.add_all([contract,agreement]);await db.flush();p=EnvelopeCreate(agreement_id=agreement.id,metric_key="sla_minutes",aggregate={"p50":30},evidence_summary={"count":20},privacy={"cohort_size":20,"epsilon":.1},idempotency_key="federated-0001");x=await create_envelope(db,oa.id,p);self.assertEqual(x.recipient_organization_id,ob.id)
   with self.assertRaises(HTTPException):await create_envelope(db,oa.id,EnvelopeCreate(agreement_id=agreement.id,metric_key="sla_minutes",aggregate={"raw_text":"secret"},privacy={"cohort_size":20},idempotency_key="federated-0002"))
   await withdraw_contract(db,oa.id,contract.id);self.assertEqual(x.status,"withdrawn");self.assertEqual(agreement.status,"suspended")
 async def test_responsibility_chain_is_forward_linked(self):
  async with self.sessions() as db:
   a,_b,oa,_ob=await self.seed(db);first=await append_responsibility(db,oa.id,a.id,ResponsibilityCreate(subject_type="action",subject_id="a1",event_type="recommended",payload={"option":"notify"}));second=await append_responsibility(db,oa.id,a.id,ResponsibilityCreate(subject_type="action",subject_id="a1",event_type="approved",payload={"decision":"yes"}));self.assertEqual(second.previous_hash,first.chain_hash);self.assertNotEqual(second.chain_hash,first.chain_hash)
 def test_marketplace_state_machine_balances_settlement_and_refund(self):
  product=IntelligenceProduct(organization_id="seller",key="risk",name="Risk",license_terms={},quality_sla={},price_cents=1000,revenue_share_percent=80,created_by="u");order=MarketplaceOrder(organization_id="seller",buyer_organization_id="buyer",product_id="p",idempotency_key="order-001",amount_cents=1000,currency="CNY",created_by="u",status="authorized");transition_order(order,product,OrderTransition(action="deliver",receipt={"license":"grant"}));transition_order(order,product,OrderTransition(action="settle"));self.assertEqual(order.settlement["seller_cents"]+order.settlement["platform_cents"],1000);transition_order(order,product,OrderTransition(action="refund",reason="SLA breach"));self.assertEqual(order.settlement["refund_cents"],1000)
 def test_secure_aggregation_discards_inputs_and_trust_is_bounded(self):
  result=secure_aggregate([10,20,30],"secure_average");self.assertEqual(result["value"],20);self.assertTrue(result["individual_values_discarded"]);self.assertEqual(trust_score(100,100,200),0)
if __name__=="__main__":unittest.main()
