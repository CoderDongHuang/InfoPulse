"""Delivery, recovery and session acceptance tests using isolated storage."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
from fastapi import FastAPI, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.api.auth import router as auth_router
from app.api.operations import router as operations_router
from app.config import get_settings
from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.models.action_loop import ActionReceipt, ActionStep, ResponseAction
from app.models.dispatch import DispatchJob
from app.models.intelligence import KnowledgeBase, KnowledgeDocument
from app.models.orchestration import ToolDefinition, ToolPolicy, WorkflowApproval, WorkflowStepRun, WorkflowVersion
from app.models.platform import ConnectorDefinition, ConnectorInstallation
from app.schemas.commercialization import ConnectorExecute
from app.schemas.multimodal import ChangeCreate
from app.services.action_loop import advance_action, create_run
from app.services.collaboration import apply_change
from app.services.commercialization import execute_connector
from app.services.dispatch import enqueue_dispatch, process_dispatch_once
from app.services.knowledge import Storage, process_knowledge_once
from app.services.orchestration import execute_one, seed_catalog
from tests import test_collaboration, test_orchestration


class DatabaseCase(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_orchestration.OrchestrationTests.asyncSetUp
    asyncTearDown = test_orchestration.OrchestrationTests.asyncTearDown
    tenant = test_orchestration.OrchestrationTests.tenant
    build = test_orchestration.OrchestrationTests.build


class ExecutionRegressions(DatabaseCase):
    async def connector(self, db, user, org, provider="slack"):
        db.add(ConnectorDefinition(key=provider, name=provider, category="messaging", write_capable=True))
        await db.flush()
        row = ConnectorInstallation(organization_id=org.id, connector_key=provider, status="approved", requested_by=user.id, config={"webhook_url": "https://example.com/hook"})
        db.add(row)
        await db.flush()
        return row

    async def test_workflow_waits_for_real_dispatch_and_sends_once(self):
        graph = {"nodes": [{"id": "start", "type": "start"}, {"id": "send", "type": "tool", "config": {"tool_key": "connector.notify", "input": {"message": "Approved notice"}}}, {"id": "end", "type": "end"}], "edges": [{"source": "start", "target": "send"}, {"source": "send", "target": "end"}]}
        async with self.sessions() as db:
            owner, _, org = await self.tenant(db)
            await self.connector(db, owner, org)
            await seed_catalog(db, org.id)
            tool = await db.scalar(select(ToolDefinition).where(ToolDefinition.key == "connector.notify"))
            db.add(ToolPolicy(organization_id=org.id, tool_id=tool.id, effect="allow", require_approval=True))
            _, _, run = await self.build(db, owner, org, graph)
            await execute_one(db, run)
            await execute_one(db, run)
            self.assertEqual(run.status, "waiting_approval")
            approval = await db.scalar(select(WorkflowApproval).where(WorkflowApproval.run_id == run.id))
            approval.status = "approved"
            run.status = "queued"
            await execute_one(db, run)
            self.assertEqual(run.status, "waiting_dispatch")
            step = await db.scalar(select(WorkflowStepRun).where(WorkflowStepRun.run_id == run.id, WorkflowStepRun.status == "waiting_dispatch"))
            step_id = step.id
            await execute_one(db, run)
            self.assertEqual(run.status, "waiting_dispatch")
            await db.commit()
            run_id = run.id
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(200, text="ok", headers={"x-request-id": "remote-1"})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            self.assertTrue(await process_dispatch_once(self.sessions, client))
            self.assertFalse(await process_dispatch_once(self.sessions, client))
        self.assertEqual(len(requests), 1)
        async with self.sessions() as db:
            from app.models.orchestration import WorkflowRun
            run = await db.get(WorkflowRun, run_id)
            await execute_one(db, run)
            self.assertEqual((await db.get(WorkflowStepRun, step_id)).status, "completed")
            self.assertEqual(run.current_node_id, "end")
            await execute_one(db, run)
            self.assertEqual(run.status, "completed")

    async def test_action_manual_then_connector_creates_verified_receipt(self):
        async with self.sessions() as db:
            owner, _, org = await self.tenant(db)
            install = await self.connector(db, owner, org)
            action = ResponseAction(organization_id=org.id, title="Response", owner_id=owner.id, created_by=owner.id)
            db.add(action)
            await db.flush()
            manual = ActionStep(organization_id=org.id, action_id=action.id, sequence=1, channel="manual")
            automatic = ActionStep(organization_id=org.id, action_id=action.id, sequence=2, channel="slack", tool_key="connector.notify", payload={"installation_id": install.id, "message": "Response complete"})
            db.add_all([manual, automatic])
            await db.flush()
            run, created = await create_run(db, action, "test-action")
            same, created_again = await create_run(db, action, "test-action")
            self.assertEqual(run.id, same.id)
            self.assertTrue(created)
            self.assertFalse(created_again)
            await advance_action(db, run)
            self.assertEqual(run.status, "waiting_receipt")
            db.add(ActionReceipt(organization_id=org.id, action_id=action.id, run_id=run.id, step_id=manual.id, channel="manual", receipt_payload={"status": "completed"}))
            await db.flush()
            await advance_action(db, run)
            self.assertEqual(run.status, "waiting_dispatch")
            await db.commit()
            run_id, action_id = run.id, action.id
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, text="ok"))) as client:
            await process_dispatch_once(self.sessions, client)
        async with self.sessions() as db:
            from app.models.action_loop import ActionRun
            run = await db.get(ActionRun, run_id)
            await advance_action(db, run)
            await advance_action(db, run)
            self.assertEqual(run.status, "completed")
            self.assertEqual((await db.get(ResponseAction, action_id)).status, "completed")
            self.assertEqual(await db.scalar(select(func.count()).select_from(ActionReceipt)), 2)

    async def test_timeout_is_unknown_and_not_retried(self):
        async with self.sessions() as db:
            owner, _, org = await self.tenant(db)
            install = await self.connector(db, owner, org)
            job = await enqueue_dispatch(db, organization_id=org.id, workspace_id=None, installation_id=install.id, message="Notice", key="timeout-0001")
            identifier = job.id
            await db.commit()
        calls = []
        def handler(request):
            calls.append(request)
            raise httpx.ReadTimeout("uncertain", request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await process_dispatch_once(self.sessions, client)
            await process_dispatch_once(self.sessions, client)
        self.assertEqual(len(calls), 1)
        async with self.sessions() as db:
            self.assertEqual((await db.get(DispatchJob, identifier)).status, "unknown")

    async def test_provider_business_error_and_changed_idempotent_input(self):
        async with self.sessions() as db:
            owner, _, org = await self.tenant(db)
            install = await self.connector(db, owner, org, "feishu")
            payload = ConnectorExecute(installation_id=install.id, provider="feishu", webhook_url="https://example.com/hook", message="Notice", idempotency_key="provider-0001")
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"code": 19001}))) as client:
                result = await execute_connector(db, org.id, payload, client)
                self.assertEqual(result.status, "failed")
                payload.message = "Different notice"
                with self.assertRaises(HTTPException) as raised:
                    await execute_connector(db, org.id, payload, client)
                self.assertEqual(raised.exception.status_code, 409)

    async def test_memory_tools_execute_and_llm_absence_does_not_charge(self):
        from app.models.orchestration import ModelRoute, PromptDefinition
        from app.services.orchestration import memory_operation, model_output, tool_guard
        async with self.sessions() as db:
            owner, _, org = await self.tenant(db)
            _, _, run = await self.build(db, owner, org)
            await seed_catalog(db, org.id)
            for key in ("memory.write", "memory.read"):
                tool = await db.scalar(select(ToolDefinition).where(ToolDefinition.key == key))
                db.add(ToolPolicy(organization_id=org.id, tool_id=tool.id, effect="allow", require_approval=False))
            step = WorkflowStepRun(organization_id=org.id, run_id=run.id, node_id="mem", node_type="tool")
            db.add(step)
            await db.flush()
            await tool_guard(db, run, {"id": "mem", "config": {"tool_key": "memory.write", "input": {"key": "memo", "value": {"answer": 42}}}}, step)
            await db.flush()
            result = await tool_guard(db, run, {"id": "mem", "config": {"tool_key": "memory.read", "input": {"key": "memo"}}}, step)
            self.assertEqual(result["value"], {"answer": 42})
            db.add_all([PromptDefinition(organization_id=org.id, key="brief", version=1, system_prompt="Brief", status="active", created_by=owner.id), ModelRoute(organization_id=org.id, task_type="general", primary_model="test", max_cost_cents=5)])
            await db.flush()
            run.budget_cents = 10
            with patch("app.services.orchestration.llm_is_configured", return_value=False):
                with self.assertRaisesRegex(RuntimeError, "unavailable"):
                    await model_output(db, run, {"config": {"prompt_key": "brief"}})
            self.assertEqual(run.spent_cents, 0)

    async def test_dispatch_scope_and_empty_action_rejected(self):
        async with self.sessions() as db:
            owner, _, org = await self.tenant(db)
            install = await self.connector(db, owner, org)
            with self.assertRaises(ValueError):
                await enqueue_dispatch(db, organization_id="other-org", workspace_id=None, installation_id=install.id, message="Notice", key="cross-tenant")
            action = ResponseAction(organization_id=org.id, title="Empty", owner_id=owner.id, created_by=owner.id)
            db.add(action)
            await db.flush()
            with self.assertRaises(ValueError):
                await create_run(db, action, "empty")


class CollaborationAcceptance(DatabaseCase):
    setup_doc = test_collaboration.CollaborationTests.setup_doc
    async def test_collaboration_creates_valid_draft_without_changing_active_version(self):
        async with self.sessions() as db:
            user, doc = await self.setup_doc(db)
            from app.models.orchestration import Workflow
            workflow = await db.get(Workflow, doc.resource_id)
            active = workflow.active_version_id
            graph = {"nodes": [{"id": "start", "type": "start"}, {"id": "review", "type": "approval"}, {"id": "end", "type": "end"}], "edges": [{"source": "start", "target": "review"}, {"source": "review", "target": "end"}]}
            await apply_change(db, doc, user.id, ChangeCreate(base_version=1, client_id="draft-browser", client_sequence=1, operations=[{"op": "set", "path": "/graph", "value": graph}]))
            draft = await db.scalar(select(WorkflowVersion).where(WorkflowVersion.workflow_id == workflow.id, WorkflowVersion.version == 2))
            self.assertEqual(draft.graph, graph)
            self.assertEqual(workflow.active_version_id, active)
            with self.assertRaises(HTTPException):
                await apply_change(db, doc, user.id, ChangeCreate(base_version=2, client_id="draft-browser", client_sequence=2, operations=[{"op": "set", "path": "/graph", "value": {}}]))
            self.assertEqual(doc.version, 2)
            self.assertEqual(await db.scalar(select(func.count()).select_from(WorkflowVersion)), 2)


class RecoveryAndSessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_http_refresh_is_single_use_and_logout_revokes_session(self):
        app = FastAPI()
        app.include_router(auth_router)
        app.include_router(operations_router)
        async def database():
            async with self.sessions() as db:
                try:
                    yield db
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
        app.dependency_overrides[get_db] = database
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            registered = await client.post("/api/v1/auth/register", json={"username": "session-user", "email": "session@example.com", "password": "secret123"})
            self.assertEqual(registered.status_code, 201, registered.text)
            login = await client.post("/api/v1/auth/login", json={"username": "session-user", "password": "secret123"})
            self.assertEqual(login.status_code, 200, login.text)
            old = login.json()
            response = await client.post("/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]})
            self.assertEqual(response.status_code, 200, response.text)
            fresh = response.json()
            reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]})
            self.assertEqual(reused.status_code, 401)
            headers = {"Authorization": "Bearer " + fresh["access_token"]}
            me = await client.get("/api/v1/auth/me", headers=headers)
            self.assertEqual(me.status_code, 200, me.text)
            legacy = create_access_token({"sub": me.json()["id"]})
            self.assertEqual((await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + legacy})).status_code, 401)
            self.assertEqual((await client.post("/api/v1/auth/logout", headers=headers)).status_code, 204)
            self.assertEqual((await client.get("/api/v1/auth/me", headers=headers)).status_code, 401)
            self.assertEqual((await client.post("/api/v1/auth/refresh", json={"refresh_token": fresh["refresh_token"]})).status_code, 401)
            with patch.object(get_settings(), "METRICS_TOKEN", ""):
                self.assertEqual((await client.get("/api/v1/metrics")).status_code, 403)

    async def test_knowledge_expired_lease_recovers_and_storage_failure_finishes(self):
        from app.models.user import User
        async with self.sessions() as db:
            user = User(username="knowledge-recovery", email="recovery@example.com", password_hash="x")
            db.add(user)
            await db.flush()
            base = KnowledgeBase(user_id=user.id, name="Recovery")
            db.add(base)
            await db.flush()
            documents = [KnowledgeDocument(user_id=user.id, knowledge_base_id=base.id, filename="recovery.md", source_type="upload", status="processing", processing_attempts=attempts, lease_until=datetime.now(timezone.utc) - timedelta(minutes=10)) for attempts in (1, 1, 3)]
            db.add_all(documents)
            await db.commit()
            identifiers = [doc.id for doc in documents]
        with tempfile.TemporaryDirectory() as directory, patch.object(get_settings(), "KNOWLEDGE_STORAGE_PATH", directory):
            store = Storage()
            store.put("staging/" + identifiers[0], b"# Verified\n\nRecovery content")
            store.put("staging/" + identifiers[1], b"unreadable")
            with patch("app.services.knowledge.storage", store):
                self.assertTrue(await process_knowledge_once(identifiers[0], self.sessions))
                with patch.object(store, "get", side_effect=OSError("storage unavailable")):
                    with self.assertRaises(OSError):
                        await process_knowledge_once(identifiers[1], self.sessions)
                self.assertFalse(await process_knowledge_once(identifiers[2], self.sessions))
            async with self.sessions() as db:
                ready, failed, exhausted = [await db.get(KnowledgeDocument, identifier) for identifier in identifiers]
                self.assertEqual(ready.status, "ready")
                self.assertEqual(ready.processing_attempts, 2)
                self.assertIsNone(ready.lease_until)
                self.assertEqual(failed.status, "failed")
                self.assertIn("storage unavailable", failed.error_message)
                self.assertEqual(exhausted.status, "failed")
