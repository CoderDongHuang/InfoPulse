import unittest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine

import app.models
from app.api.orchestration import decide
from app.core.database import Base
from app.models.enterprise import OrganizationMember
from app.models.orchestration import EvaluationDataset,ModelRoute,PromptDefinition,ToolDefinition,Workflow,WorkflowApproval,WorkflowRun,WorkflowStepRun,WorkflowVersion
from app.models.user import User
from app.schemas.orchestration import ApprovalDecision
from app.services.enterprise import provision_personal_tenant,resolve_tenant
from app.services.orchestration import evaluate,execute_one,seed_catalog,validate_graph

SIMPLE={"nodes":[{"id":"start","type":"start"},{"id":"review","type":"approval","config":{"summary":"External action review"}},{"id":"end","type":"end"}],"edges":[{"source":"start","target":"review"},{"source":"review","target":"end"}]}

class OrchestrationTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.engine=create_async_engine("sqlite+aiosqlite:///:memory:");self.sessions=async_sessionmaker(self.engine,expire_on_commit=False)
  async with self.engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
 async def asyncTearDown(self):await self.engine.dispose()
 async def tenant(self,db):
  owner=User(username="owner",email="owner@agent.test",password_hash="x");approver=User(username="approver",email="approver@agent.test",password_hash="x");db.add_all([owner,approver]);await db.flush();org=await provision_personal_tenant(db,owner);db.add(OrganizationMember(organization_id=org.id,user_id=approver.id,role_key="admin"));await db.flush();return owner,approver,org
 async def build(self,db,owner,org,graph=SIMPLE):
  workflow=Workflow(organization_id=org.id,name="Governed workflow",created_by=owner.id,status="active");db.add(workflow);await db.flush();version=WorkflowVersion(organization_id=org.id,workflow_id=workflow.id,version=1,graph=validate_graph(graph),created_by=owner.id);db.add(version);await db.flush();workflow.active_version_id=version.id;run=WorkflowRun(organization_id=org.id,workflow_id=workflow.id,version_id=version.id,user_id=owner.id,idempotency_key="test-run-0001");db.add(run);await db.flush();return workflow,version,run
 def test_graph_rejects_cycles_and_unreachable_nodes(self):
  graph={"nodes":[{"id":"start","type":"start"},{"id":"loop","type":"condition"},{"id":"end","type":"end"}],"edges":[{"source":"start","target":"loop"},{"source":"loop","target":"start"}]}
  with self.assertRaises(ValueError):validate_graph(graph)
 async def test_durable_run_waits_for_separate_approver_then_resumes(self):
  async with self.sessions() as db:
   owner,approver,org=await self.tenant(db);_workflow,_version,run=await self.build(db,owner,org)
   await execute_one(db,run);self.assertEqual(run.current_node_id,"review")
   await execute_one(db,run);self.assertEqual(run.status,"waiting_approval");approval=next(x for x in db.new if isinstance(x,WorkflowApproval));await db.flush()
   owner_ctx=await resolve_tenant(db,owner,org.id,None)
   with self.assertRaises(Exception):await decide(approval.id,ApprovalDecision(decision="approved",note="self review"),owner_ctx,owner,db)
   approver_ctx=await resolve_tenant(db,approver,org.id,None);await decide(approval.id,ApprovalDecision(decision="approved",note="evidence reviewed"),approver_ctx,approver,db)
   await execute_one(db,run);self.assertEqual(run.current_node_id,"end");await execute_one(db,run);self.assertEqual(run.status,"completed")
 async def test_tool_policy_defaults_to_deny(self):
  graph={"nodes":[{"id":"start","type":"start"},{"id":"tool","type":"tool","config":{"tool_key":"memory.read"}},{"id":"end","type":"end"}],"edges":[{"source":"start","target":"tool"},{"source":"tool","target":"end"}]}
  async with self.sessions() as db:
   owner,_approver,org=await self.tenant(db);await seed_catalog(db,org.id);_w,_v,run=await self.build(db,owner,org,graph);await execute_one(db,run);await execute_one(db,run);self.assertEqual(run.status,"failed");step=await db.scalar(select(WorkflowStepRun).where(WorkflowStepRun.run_id==run.id,WorkflowStepRun.node_id=="tool"));self.assertIn("denied",step.error)
 async def test_cost_budget_is_checked_before_model_call(self):
  graph={"nodes":[{"id":"start","type":"start"},{"id":"agent","type":"agent","config":{"prompt_key":"brief","task_type":"summary","estimated_cost_cents":5}},{"id":"end","type":"end"}],"edges":[{"source":"start","target":"agent"},{"source":"agent","target":"end"}]}
  async with self.sessions() as db:
   owner,_approver,org=await self.tenant(db);db.add_all([PromptDefinition(organization_id=org.id,key="brief",version=1,system_prompt="Summarize only supplied evidence.",status="active",created_by=owner.id),ModelRoute(organization_id=org.id,task_type="summary",primary_model="test-model",max_cost_cents=5)]);_w,_v,run=await self.build(db,owner,org,graph);run.budget_cents=0;await execute_one(db,run);await execute_one(db,run);self.assertEqual(run.status,"failed");self.assertEqual(run.spent_cents,0)
 async def test_evaluation_gate_detects_forbidden_tool(self):
  graph={"nodes":[{"id":"start","type":"start"},{"id":"tool","type":"tool","config":{"tool_key":"connector.notify"}},{"id":"end","type":"end"}],"edges":[{"source":"start","target":"tool"},{"source":"tool","target":"end"}]}
  async with self.sessions() as db:
   owner,_approver,org=await self.tenant(db);_w,version,_run=await self.build(db,owner,org,graph);dataset=EvaluationDataset(organization_id=org.id,name="Safety",cases=[{"name":"no outbound","input":{},"forbidden_tools":["connector.notify"]}],thresholds={"minimum_score":1},created_by=owner.id);db.add(dataset);await db.flush();result=await evaluate(db,dataset,version);self.assertFalse(result.passed);self.assertEqual(result.score,0)

if __name__=="__main__":unittest.main()
