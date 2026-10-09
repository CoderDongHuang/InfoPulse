"""Regression scenarios reproduced in the October audit."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.api.action_loop import router as action_router
from app.api.hot_search import router as hot_router
from app.api.sources import router as source_router
from app.config import get_settings
from app.core.database import Base, get_db
from app.core.outbound import public_addresses, public_request
from app.dependencies import get_current_user, get_tenant_context
from app.models.action_loop import ResponseAction, ActionRun, ActionStep, ActionReceipt
from app.models.user import User
from app.schemas.auth import UserRegisterRequest
from app.services.auth_service import register_user
from app.services.collectors.rss import RssCollector
from app.services.enterprise import provision_personal_tenant, resolve_tenant
from app.services.orchestration import next_node, validate_graph


class OutboundTests(unittest.IsolatedAsyncioTestCase):
    async def test_redirect_to_private_address_is_never_sent(self):
        requests = []
        def handler(request):
            requests.append(str(request.url))
            return httpx.Response(302, headers={"location": "http://127.0.0.1/internal"})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
            with self.assertRaises(ValueError):
                await RssCollector("https://example.com/feed", client).collect()
        self.assertEqual(requests, ["https://example.com/feed"])

    async def test_oversize_and_post_redirect_rejected(self):
        for response in (httpx.Response(200, content=b"x" * 101), httpx.Response(307, headers={"location": "https://example.com/next"})):
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: response)) as client:
                with self.assertRaises(ValueError):
                    await public_request("POST", "https://example.com", client=client, max_bytes=100)

    def test_mixed_dns_and_reserved_targets_rejected(self):
        with patch("socket.getaddrinfo", return_value=[(2,1,6,'',('93.184.216.34',443)),(2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaises(ValueError):public_addresses("https://example.com")
        for url in ("https://[::1]/", "http://100.64.0.1/", "https://example.com:8443", "https://user:pass@example.com"):
            with self.assertRaises(ValueError):public_addresses(url, resolve_dns=False)

    async def test_dns_pinned_and_tls_hostname_preserved(self):
        requests=[]
        class RecordingTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                requests.append(request)
                return httpx.Response(200, content=b"ok")
        with patch("socket.getaddrinfo", return_value=[(2,1,6,'',('93.184.216.34',443))]) as dns:
            async with httpx.AsyncClient(transport=RecordingTransport()) as client:
                await public_request("GET", "https://example.com/feed", client=client)
        self.assertEqual(dns.call_count,1)
        self.assertEqual(requests[0].url.host,"93.184.216.34")
        self.assertEqual(requests[0].headers["host"],"example.com")
        self.assertEqual(requests[0].extensions["sni_hostname"],"example.com")


class AuditApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine=create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions=async_sessionmaker(self.engine,expire_on_commit=False)
        async with self.engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):await self.engine.dispose()

    async def test_registration_cannot_claim_admin_email(self):
        async with self.sessions() as db:
            with patch.object(get_settings(),"ADMIN_EMAILS",["admin@example.com"]):
                await register_user(db,UserRegisterRequest(username="admin-claim",email="admin@example.com",password="secret123"))
            user=await db.scalar(select(User).where(User.email=="admin@example.com"))
            self.assertFalse(user.is_admin)

    async def test_receipt_http_roundtrip_ownership_and_sqlite_due_date(self):
        async with self.sessions() as db:
            user=User(username="audit",email="audit@example.com",password_hash="x");db.add(user);await db.flush()
            org=await provision_personal_tenant(db,user);ctx=await resolve_tenant(db,user,org.id,None)
            action=ResponseAction(organization_id=org.id,title="Audit action",owner_id=user.id,created_by=user.id,due_at=datetime.now(timezone.utc)-timedelta(days=1))
            other=ResponseAction(organization_id=org.id,title="Other action",owner_id=user.id,created_by=user.id)
            db.add_all([action,other]);await db.flush()
            run=ActionRun(organization_id=org.id,action_id=action.id,idempotency_key="audit")
            wrong=ActionStep(organization_id=org.id,action_id=other.id,sequence=1,channel="manual")
            db.add_all([run,wrong]);await db.commit();await db.refresh(action)
            self.assertIsNone(action.due_at.tzinfo)
            app=FastAPI();app.include_router(action_router)
            async def database():yield db
            app.dependency_overrides[get_db]=database
            app.dependency_overrides[get_tenant_context]=lambda:ctx
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://testserver") as client:
                result=await client.post(f"/api/v1/actions/{action.id}/receipts",json={"run_id":run.id,"channel":"manual"})
                self.assertEqual(result.status_code,201,result.text)
                detail=await client.get(f"/api/v1/actions/{action.id}")
                self.assertEqual(detail.json()["receipts"][0]["id"],result.json()["id"])
                result=await client.post(f"/api/v1/actions/{action.id}/receipts",json={"step_id":wrong.id,"channel":"manual"})
                self.assertEqual(result.status_code,422)
                result=await client.get("/api/v1/action-operations")
                self.assertEqual(result.status_code,200,result.text)
                self.assertIn(action.id,result.json()["overdue_action_ids"])

    async def test_shared_source_writes_reject_normal_user(self):
        app=FastAPI();app.include_router(source_router)
        app.dependency_overrides[get_current_user]=lambda:User(is_admin=False)
        async def database():yield None
        app.dependency_overrides[get_db]=database
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://testserver") as client:
            for method,url,data in (("POST","/rss",{"name":"Feed","feed_url":"https://example.com"}),("PATCH","/source",{"enabled":False}),("DELETE","/source",None),("POST","/source/sync",None),("POST","/source/test",None),("POST","/rss/validate",{"feed_url":"https://example.com"})):
                result=await client.request(method,"/api/v1/sources"+url,json=data)
                self.assertEqual(result.status_code,403,result.text)

    async def test_anonymous_explanation_rejected_before_service(self):
        app=FastAPI();app.include_router(hot_router)
        with patch("app.api.hot_search.explain_hot_item") as explain:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://testserver") as client:
                result=await client.post("/api/v1/hot-search/explain",json={})
            self.assertIn(result.status_code,(401,403));explain.assert_not_called()


class BranchTests(unittest.TestCase):
    def test_false_result_cannot_take_true_edge(self):
        graph={"edges":[{"source":"check","target":"send","condition":"true"}]}
        with self.assertRaises(ValueError):next_node(graph,"check",{"result":False})
        graph["edges"].append({"source":"check","target":"stop","condition":"default"})
        self.assertEqual(next_node(graph,"check",{"result":False}),"stop")

    def test_ambiguous_graph_rejected(self):
        graph={"nodes":[{"id":"start","type":"start"},{"id":"end","type":"end"},{"id":"other","type":"end"}],"edges":[{"source":"start","target":"end"},{"source":"start","target":"other"}]}
        with self.assertRaises(ValueError):validate_graph(graph)
