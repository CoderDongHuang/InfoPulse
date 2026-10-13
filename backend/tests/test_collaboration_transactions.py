"""REST responses must expose committed collaboration data to WS connections."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.api import multimodal as api
from app.api import orchestration
from app.core.database import Base
from app.models.multimodal import CollaborationAudit, CollaborationTicket, CollaborativeDocument
from app.models.orchestration import OrchestrationAudit, Workflow, WorkflowVersion
from app.models.user import User
from app.schemas.multimodal import CollabOpen
from app.schemas.orchestration import WorkflowCreate
from app.services.enterprise import provision_personal_tenant


class CollaborationTransactionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine("sqlite+aiosqlite:///" + str(Path(self.tmp.name) / "audit.db"))
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.sessions() as db:
            self.user = User(username="collab-tx", email="collab-tx@example.com", password_hash="x")
            db.add(self.user)
            await db.flush()
            org = await provision_personal_tenant(db, self.user)
            self.ctx = SimpleNamespace(organization=org)
            self.workflow = Workflow(organization_id=org.id, name="transaction fixture", created_by=self.user.id)
            db.add(self.workflow)
            await db.commit()

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.tmp.cleanup()

    async def open(self, db):
        with patch.object(api, "require_permission"), patch.object(api, "workspace"), patch.object(api, "verify_resource", AsyncMock(return_value={"graph": {}})):
            return await api.open_document(CollabOpen(resource_type="workflow", resource_id=self.workflow.id), self.ctx, self.user, db)

    async def test_document_audit_and_ticket_visible_before_dependency_exit(self):
        async with self.sessions() as writer:
            document = await self.open(writer)
            async with self.sessions() as reader:
                self.assertIsNotNone(await reader.get(CollaborativeDocument, document["id"]))
                self.assertIsNotNone(await reader.scalar(select(CollaborationAudit).where(CollaborationAudit.document_id == document["id"])))
            with patch.object(api, "require_permission"):
                result = await api.ticket(document["id"], self.ctx, self.user, writer)
            # Independent socket DB connection, while writer/dependency is still open.
            async with self.sessions() as reader:
                row = await reader.scalar(select(CollaborationTicket).where(CollaborationTicket.ticket_hash == hashlib.sha256(result["ticket"].encode()).hexdigest()))
                self.assertIsNotNone(row)
                self.assertEqual(row.document_id, document["id"])
                self.assertEqual(row.user_id, self.user.id)
                self.assertIsNone(row.consumed_at)

    async def test_document_commit_failure_cannot_return_success(self):
        async with self.sessions() as writer:
            with patch.object(writer, "commit", AsyncMock(side_effect=RuntimeError("commit rejected"))):
                with self.assertRaisesRegex(RuntimeError, "commit rejected"):
                    await self.open(writer)

    async def test_ticket_commit_failure_cannot_return_success(self):
        async with self.sessions() as writer:
            document = await self.open(writer)
            with patch.object(api, "require_permission"), patch.object(writer, "commit", AsyncMock(side_effect=RuntimeError("commit rejected"))):
                with self.assertRaisesRegex(RuntimeError, "commit rejected"):
                    await api.ticket(document["id"], self.ctx, self.user, writer)

    async def test_workflow_and_version_visible_to_immediate_collaboration_request(self):
        graph = {"nodes": [{"id": "start", "type": "start"}, {"id": "end", "type": "end"}], "edges": [{"source": "start", "target": "end"}]}
        async with self.sessions() as writer:
            with patch.object(orchestration, "require_permission"):
                result = await orchestration.create_workflow(WorkflowCreate(name="committed workflow", graph=graph), self.ctx, self.user, writer)
            async with self.sessions() as reader:
                workflow = await reader.get(Workflow, result["id"])
                self.assertIsNotNone(workflow)
                version = await reader.get(WorkflowVersion, result["active_version_id"])
                self.assertEqual(version.workflow_id, workflow.id)
                audit = await reader.scalar(select(OrchestrationAudit).where(OrchestrationAudit.action == "workflow.created"))
                self.assertEqual(audit.details["workflow_id"], workflow.id)
                # Use the actual cross-domain ownership lookup, not a mocked verifier.
                snapshot = await api.verify_resource(reader, self.ctx, "workflow", workflow.id)
                self.assertEqual(snapshot["graph"], graph)

    async def test_workflow_commit_failure_cannot_return_success(self):
        graph = {"nodes": [{"id": "start", "type": "start"}, {"id": "end", "type": "end"}], "edges": [{"source": "start", "target": "end"}]}
        async with self.sessions() as writer:
            with patch.object(orchestration, "require_permission"), patch.object(writer, "commit", AsyncMock(side_effect=RuntimeError("commit rejected"))):
                with self.assertRaisesRegex(RuntimeError, "commit rejected"):
                    await orchestration.create_workflow(WorkflowCreate(name="rejected workflow", graph=graph), self.ctx, self.user, writer)
