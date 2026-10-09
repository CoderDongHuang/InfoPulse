"""Cross-worker limiter, signed delivery and total LLM budget regression tests."""
import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.api.platform import replay, test_webhook as render_webhook
from app.core.database import Base
from app.core import llm
from app.middleware.rate_limit import RateLimitMiddleware, consume_window
from app.models.platform import WebhookDelivery, WebhookEndpoint
from app.services.platform import cipher, process_webhook_once, verify_webhook
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.platform import WebhookTest
from app.services.enterprise import provision_personal_tenant, resolve_tenant


class LimiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_workers_share_atomic_window(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_async_engine("sqlite+aiosqlite:///" + Path(directory, "limits.db").as_posix())
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            try:
                async with engine.begin() as connection:
                    await connection.run_sync(Base.metadata.create_all)
                outcomes = await asyncio.gather(*(consume_window(sessions, "shared-user", 5, 120) for _ in range(20)))
                self.assertEqual(sum(outcomes), 5)
                self.assertTrue(await consume_window(sessions, "shared-user", 5, 180))
                app = FastAPI()
                app.add_middleware(RateLimitMiddleware, sessions=sessions)
                @app.post("/api/v1/auth/login")
                async def login():
                    return {"ok": True}
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                    responses = [await client.post("/api/v1/auth/login") for _ in range(11)]
                self.assertEqual([r.status_code for r in responses], [200] * 10 + [429])
                self.assertIn("retry-after", responses[-1].headers)
            finally:
                await engine.dispose()

    async def test_storage_failure_fails_closed(self):
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware)
        with patch("app.middleware.rate_limit.consume_window", side_effect=OSError("offline")):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                response = await client.post("/api/v1/auth/login")
        self.assertEqual(response.status_code, 503)


class SignedDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with self.sessions() as db:
            user = User(username="webhook-owner", email="webhook@example.com", password_hash="x")
            db.add(user)
            await db.flush()
            org = await provision_personal_tenant(db, user)
            self.ctx = await resolve_tenant(db, user, org.id, None)
            endpoint = WebhookEndpoint(organization_id=org.id, name="Audit", target_url="https://example.com/hook",
                event_types=["event.created"], secret_hash="unused", secret_ciphertext=cipher().encrypt(b"test-secret").decode())
            db.add(endpoint)
            await db.commit()
            self.endpoint_id = endpoint.id

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_sandbox_does_not_send_and_external_delivery_is_signed(self):
        async with self.sessions() as db:
            sandbox = await render_webhook(self.endpoint_id, WebhookTest(event_type="event.created"), self.ctx, db)
            queued = await render_webhook(self.endpoint_id, WebhookTest(event_type="event.created"), self.ctx, db, True)
            self.assertEqual(sandbox["status"], "sandboxed")
            self.assertFalse(queued["sent"])
            await db.commit()
        requests = []
        def handler(request):
            requests.append(request)
            self.assertTrue(verify_webhook("test-secret", request.headers["InfoPulse-Timestamp"],
                request.headers["InfoPulse-Event-ID"], request.content, request.headers["InfoPulse-Signature"]))
            return httpx.Response(204)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            self.assertTrue(await process_webhook_once(self.sessions, client))
            self.assertFalse(await process_webhook_once(self.sessions, client))
        self.assertEqual(len(requests), 1)
        async with self.sessions() as db:
            self.assertEqual((await db.get(WebhookDelivery, queued["delivery_id"])).status, "delivered")
            self.assertEqual((await db.get(WebhookDelivery, sandbox["delivery_id"])).status, "sandboxed")

    async def test_expired_claim_is_unknown_and_requires_explicit_replay(self):
        async with self.sessions() as db:
            queued = await render_webhook(self.endpoint_id, WebhookTest(event_type="event.created"), self.ctx, db, True)
            row = await db.get(WebhookDelivery, queued["delivery_id"])
            row.status = "running"
            row.next_attempt_at = datetime.now(timezone.utc) - timedelta(minutes=3)
            await db.commit()
        self.assertFalse(await process_webhook_once(self.sessions))
        async with self.sessions() as db:
            row = await db.get(WebhookDelivery, queued["delivery_id"])
            self.assertEqual(row.status, "unknown")
            replayed = await replay(row.id, self.ctx, db, True)
            self.assertEqual(replayed["status"], "queued")
            self.assertEqual(replayed["attempt"], 2)


class LLMBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_call_cancels_at_total_budget(self):
        cancelled = asyncio.Event()
        async def create(**kwargs):
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.object(llm, "get_llm_client", return_value=client), patch.object(llm.settings, "LLM_TIMEOUT_SECONDS", 0.02):
            with self.assertRaises(asyncio.TimeoutError):
                await llm.complete_chat("System", "Message")
        self.assertTrue(cancelled.is_set())

    async def test_stream_has_total_budget_and_closes(self):
        class Stream:
            def __aiter__(self):
                return self
            async def __anext__(self):
                await asyncio.sleep(0.015)
                return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="chunk"))])
            close = AsyncMock()
        stream = Stream()
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=stream))))
        chunks = []
        with patch.object(llm, "get_llm_client", return_value=client), patch.object(llm.settings, "LLM_TIMEOUT_SECONDS", 0.04):
            with self.assertRaises(asyncio.TimeoutError):
                async for chunk in llm.stream_chat("System", "Message"):
                    chunks.append(chunk)
        self.assertGreater(len(chunks), 0)
        stream.close.assert_awaited_once()
