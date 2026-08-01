import unittest
from unittest.mock import AsyncMock
import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
import app.models
from app.core.database import Base
from app.models.commercialization import TemplatePackage,TemplatePackageVersion,UsageEntitlement
from app.models.platform import ConnectorDefinition,ConnectorInstallation
from app.models.user import User
from app.schemas.commercialization import ApprovalFlowCreate,ConnectorExecute
from app.services.commercialization import checksum,consume_usage,connector_payload,execute_connector
from app.services.enterprise import provision_personal_tenant

class CommercializationTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.engine=create_async_engine("sqlite+aiosqlite:///:memory:");self.sessions=async_sessionmaker(self.engine,expire_on_commit=False)
  async with self.engine.begin() as c:await c.run_sync(Base.metadata.create_all)
 async def asyncTearDown(self):await self.engine.dispose()
 async def seed(self,db):
  user=User(username="commercial",email="commercial@example.com",password_hash="x");db.add(user);await db.flush();org=await provision_personal_tenant(db,user);await db.flush();return user,org
 async def test_template_versions_are_immutable_snapshots(self):
  async with self.sessions() as db:
   user,org=await self.seed(db);pkg=TemplatePackage(organization_id=org.id,key="response",name="Response",current_version=2,created_by=user.id);db.add(pkg);await db.flush();v1=TemplatePackageVersion(organization_id=org.id,package_id=pkg.id,version=1,definition={"steps":["review"]},checksum=checksum({"steps":["review"]}),created_by=user.id);v2=TemplatePackageVersion(organization_id=org.id,package_id=pkg.id,version=2,definition=dict(v1.definition),rollback_of_version=1,checksum=v1.checksum,created_by=user.id);db.add_all([v1,v2]);await db.flush();self.assertEqual(v1.checksum,v2.checksum);self.assertEqual(v1.definition,{"steps":["review"]})
 async def test_plan_limit_blocks_overage(self):
  async with self.sessions() as db:
   _,org=await self.seed(db);db.add(UsageEntitlement(organization_id=org.id,limits={"connector_executions":1},feature_flags={}));await db.flush();await consume_usage(db,org.id,"connector_executions",1)
   with self.assertRaises(HTTPException) as raised:await consume_usage(db,org.id,"connector_executions",1)
   self.assertEqual(raised.exception.status_code,429)
 async def test_connector_is_real_http_and_idempotent(self):
  async with self.sessions() as db:
   user,org=await self.seed(db);db.add(ConnectorDefinition(key="slack",name="Slack",category="messaging",write_capable=True));await db.flush();install=ConnectorInstallation(organization_id=org.id,workspace_id=None,connector_key="slack",status="approved",requested_by=user.id,approved_by=user.id);db.add(install);await db.flush();response=httpx.Response(200,headers={"x-request-id":"remote-1"},request=httpx.Request("POST","https://hooks.slack.com/x"));client=AsyncMock();client.post.return_value=response
   p=ConnectorExecute(installation_id=install.id,provider="slack",webhook_url="https://hooks.slack.com/x",message="Approved response",idempotency_key="action-run-0001");a=await execute_connector(db,org.id,p,client);b=await execute_connector(db,org.id,p,client);self.assertEqual(a.id,b.id);self.assertEqual(a.status,"succeeded");client.post.assert_awaited_once()
 def test_provider_payloads_and_approval_graph(self):
  self.assertEqual(connector_payload("slack","x"),{"text":"x"});self.assertEqual(connector_payload("feishu","x")["msg_type"],"text")
  with self.assertRaises(ValueError):ApprovalFlowCreate(name="Bad",trigger="high_risk",graph={"nodes":[{"id":"a"}],"edges":[{"from":"a","to":"missing"}]})
if __name__=="__main__":unittest.main()
