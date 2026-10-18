"""Account isolation, write-only credentials, outbound safety and real API contracts."""
import asyncio
import json
import ssl
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.api.service_settings import router
from app.config import get_settings
from app.core import llm
from app.core.database import Base, get_db
from app.core.errors import setup_error_handlers
from app.core.private_clients import PublicModelTransport, BoundedStream, smtp_connection
from app.core.runtime_settings import get_runtime_settings, use_settings
from app.core.security import create_access_token
from app.dependencies import get_configured_user
from app.models.auth_session import AuthSession
from app.models.service_settings import UserServiceSettings
from app.models.user import User
from app.schemas.service_settings import ServiceSettingsUpdate
from app.services.service_settings import owner_settings


class PrivateSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.master = patch.object(get_settings(), "PLATFORM_ENCRYPTION_KEY", "fixture-independent-encryption-key-20261018")
        self.master.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine("sqlite+aiosqlite:///" + str(Path(self.tmp.name) / "private.db"))
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.users = []
        self.headers = []
        async with self.sessions() as db:
            for name in ("private-a", "private-b"):
                user = User(username=name, email=name + "@example.com", password_hash="x")
                db.add(user)
                await db.flush()
                db.add(AuthSession(id=name, user_id=user.id, refresh_jti=name, expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
                self.users.append(user)
                self.headers.append({"Authorization": "Bearer " + create_access_token({"sub": user.id, "sid": name})})
            await db.commit()
        self.app = FastAPI()
        setup_error_handlers(self.app)
        self.app.include_router(router)
        async def database():
            async with self.sessions() as db:
                yield db
        self.app.dependency_overrides[get_db] = database
        @self.app.get("/probe")
        async def probe(user=Depends(get_configured_user)):
            async def stream():
                await asyncio.sleep(0)
                yield await llm.complete_chat("system", "test")
            return StreamingResponse(stream())
        self.http = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver")

    async def asyncTearDown(self):
        await self.http.aclose()
        await self.engine.dispose()
        self.tmp.cleanup()
        self.master.stop()

    async def save(self, index=0, revision=0, **changes):
        payload = {"revision": revision, **changes}
        return await self.http.put("/api/v1/settings/services", json=payload, headers=self.headers[index])

    async def test_auth_encryption_no_echo_owner_isolation_retention_clear_and_revision(self):
        self.assertIn((await self.http.get("/api/v1/settings/services")).status_code, (401, 403))
        response = await self.save(llm_api_key="account-a-secret", smtp_password="mail-a-secret")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("account-a-secret", response.text)
        self.assertNotIn("mail-a-secret", response.text)
        self.assertNotIn("llm_api_key", response.json())
        self.assertTrue(response.json()["llm_api_key_configured"])
        async with self.sessions() as db:
            stored = await db.get(UserServiceSettings, self.users[0].id)
            self.assertNotIn("account-a-secret", stored.ciphertext)
            self.assertEqual((await owner_settings(db, self.users[0].id)).LLM_API_KEY, "account-a-secret")
            self.assertEqual((await owner_settings(db, self.users[1].id)).LLM_API_KEY, "")
        other = await self.http.get("/api/v1/settings/services", headers=self.headers[1])
        self.assertEqual(other.json()["revision"], 0)
        self.assertFalse(other.json()["llm_api_key_configured"])
        self.assertEqual((await self.save(revision=0)).status_code, 409)
        kept = await self.save(revision=1, llm_model="new-model")
        self.assertEqual(kept.status_code, 200)
        self.assertTrue(kept.json()["llm_api_key_configured"])
        cleared = await self.save(revision=2, clear_secrets=["llm_api_key", "smtp_password"])
        self.assertEqual(cleared.status_code, 200)
        self.assertFalse(cleared.json()["llm_api_key_configured"])
        self.assertFalse(cleared.json()["smtp_password_configured"])

    async def test_destination_change_cannot_forward_retained_credentials(self):
        self.assertEqual((await self.save(llm_api_key="key-a", smtp_host="smtp.example.com", smtp_password="mail-a")).status_code, 200)
        self.assertEqual((await self.save(revision=1, llm_api_base="https://other.example.com/v1")).status_code, 422)
        self.assertEqual((await self.save(revision=1, smtp_host="other.example.com")).status_code, 422)
        self.assertEqual((await self.save(revision=1, llm_api_base="https://other.example.com/v1", llm_api_key="key-b", smtp_host="smtp.example.com")).status_code, 200)

    async def test_invalid_inputs_do_not_echo_secrets_or_allow_private_destinations(self):
        for endpoint in ("http://example.com/v1", "https://127.0.0.1", "https://[::1]", "https://169.254.169.254", "https://localhost/v1", "https://user:pw@example.com", "https://example.com:8443", "https://example.com/v1?key=secret", "https://example.com:bad", "https://[invalid]"):
            response = await self.save(llm_api_base=endpoint, llm_api_key="hidden-test-key")
            self.assertEqual(response.status_code, 422, response.text)
            self.assertNotIn("hidden-test-key", response.text)
        for payload in ({"smtp_port": 25}, {"smtp_host": "localhost"}, {"smtp_host": "10.0.0.1"}, {"smtp_from": "bad\nheader"}, {"llm_api_key": "hidden-test-key\n"}, {"llm_model": "   "}, {"user_id": self.users[1].id}):
            response = await self.save(**payload)
            self.assertEqual(response.status_code, 422, response.text)
            self.assertNotIn("hidden-test-key", response.text)

    async def test_missing_or_rotated_encryption_key_fails_closed(self):
        with patch.object(get_settings(), "PLATFORM_ENCRYPTION_KEY", ""):
            self.assertEqual((await self.save(llm_api_key="key-a")).status_code, 503)
        await self.save(llm_api_key="key-a")
        with patch.object(get_settings(), "PLATFORM_ENCRYPTION_KEY", "a-different-independent-master-key-32-chars"):
            response = await self.http.get("/api/v1/settings/services", headers=self.headers[0])
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("key-a", response.text)

    async def test_streaming_concurrent_accounts_use_own_clients_and_close(self):
        await self.save(llm_api_key="key-a", llm_model="model-a")
        await self.save(index=1, llm_api_key="key-b", llm_model="model-b")
        calls, clients = [], []
        def factory():
            key = get_runtime_settings().LLM_API_KEY
            async def create(**kwargs):
                await asyncio.sleep(.01)
                calls.append((key, kwargs["model"]))
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=kwargs["model"]))])
            client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)), close=AsyncMock())
            clients.append(client)
            return client
        with patch.object(llm, "get_llm_client", side_effect=factory):
            results = await asyncio.gather(*(self.http.get("/probe", headers=self.headers[i]) for i in (0, 1, 0, 1)))
        self.assertEqual([r.text for r in results], ["model-a", "model-b", "model-a", "model-b"])
        self.assertEqual(sorted(calls), [("key-a", "model-a")] * 2 + [("key-b", "model-b")] * 2)
        for client in clients:
            client.close.assert_awaited_once()
        self.assertNotEqual(get_runtime_settings().LLM_API_KEY, "key-a")

    async def test_saved_model_connection_test_hides_provider_errors(self):
        await self.save(llm_api_key="key-a")
        with patch("app.api.service_settings.complete_chat", AsyncMock(return_value="OK")) as model:
            result = await self.http.post("/api/v1/settings/services/test/llm", headers=self.headers[0])
            self.assertEqual(result.status_code, 200)
            self.assertEqual(model.await_count, 1)
        with patch("app.api.service_settings.complete_chat", AsyncMock(side_effect=RuntimeError("provider reflected key-a"))):
            result = await self.http.post("/api/v1/settings/services/test/llm", headers=self.headers[0])
            self.assertEqual(result.status_code, 400)
            self.assertNotIn("key-a", result.text)

    async def test_background_media_and_workflow_bind_owner_instead_of_request(self):
        await self.save(llm_api_key="key-a")
        await self.save(index=1, llm_api_key="key-b")
        async def inspect(*args):
            return get_runtime_settings().LLM_API_KEY
        from app.services import multimodal, orchestration
        async with self.sessions() as db:
            outer = await owner_settings(db, self.users[1].id)
            with use_settings(outer):
                with patch.object(multimodal, "_process_asset", side_effect=inspect), patch.object(orchestration, "_model_output", side_effect=inspect):
                    self.assertEqual(await multimodal.process_asset(db, SimpleNamespace(user_id=self.users[0].id), None), "key-a")
                    self.assertEqual(await orchestration.model_output(db, SimpleNamespace(user_id=self.users[0].id), None), "key-a")
                self.assertEqual(get_runtime_settings().LLM_API_KEY, "key-b")

    async def test_concurrent_first_save_has_one_winner(self):
        responses = await asyncio.gather(self.save(llm_api_key="key-one"), self.save(llm_api_key="key-two"))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409])

    async def test_real_sdk_uses_each_saved_endpoint_credential_model_and_closes_http(self):
        await self.save(llm_api_key="key-a", llm_model="model-a", llm_api_base="https://a.example.com/v1")
        await self.save(index=1, llm_api_key="key-b", llm_model="model-b", llm_api_base="https://b.example.com/v1")
        seen, clients = [], []
        async def respond(request):
            body = json.loads(request.content)
            seen.append((str(request.url), request.headers["authorization"], body["model"]))
            return httpx.Response(200, json={"id": "fixture", "object": "chat.completion", "created": 0,
                "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": body["model"]}}]})
        def http_client(_):
            client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
            clients.append(client)
            return client
        with patch.object(llm, "model_http_client", side_effect=http_client):
            results = await asyncio.gather(*(self.http.get("/probe", headers=self.headers[i]) for i in (0, 1)))
        self.assertEqual([r.text for r in results], ["model-a", "model-b"])
        self.assertEqual(sorted(seen), [("https://a.example.com/v1/chat/completions", "Bearer key-a", "model-a"), ("https://b.example.com/v1/chat/completions", "Bearer key-b", "model-b")])
        self.assertTrue(all(client.is_closed for client in clients))

    async def test_email_delivery_uses_notification_owner_and_does_not_persist_provider_secrets(self):
        from app.models.intelligence import DeliveryAttempt
        from app.services.automation import create_notification, deliver_attempt, preference_for
        await self.save(smtp_host="smtp.example.com", smtp_username="owner-a", smtp_password="mail-a", smtp_from="a@example.com")
        await self.save(index=1, smtp_host="smtp-b.example.com", smtp_password="mail-b", smtp_from="b@example.com")
        observed = []
        sender = Mock()
        @contextmanager
        def connection(settings):
            observed.append((settings.SMTP_HOST, settings.SMTP_PASSWORD))
            yield sender
        async with self.sessions() as db:
            preference = await preference_for(db, self.users[0].id)
            preference.email_enabled = True
            preference.email_address = "receiver@example.com"
            notification = await create_notification(db, self.users[0].id, "report", "fixture", "fixture body")
            attempt = DeliveryAttempt(notification_id=notification.id, channel="email")
            db.add(attempt)
            await db.commit()
            with use_settings(await owner_settings(db, self.users[1].id)), patch("app.core.private_clients.smtp_connection", connection):
                await deliver_attempt(db, attempt)
                self.assertEqual(attempt.status, "delivered")
                message = sender.send_message.call_args.args[0]
                self.assertEqual(message["From"], "a@example.com")
                self.assertEqual(message["To"], "receiver@example.com")
                sender.send_message.side_effect = RuntimeError("provider echoed mail-a")
                await deliver_attempt(db, attempt)
                self.assertNotIn("mail-a", attempt.error_message)
                self.assertEqual(attempt.status, "retrying")
        self.assertEqual(observed, [("smtp.example.com", "mail-a")] * 2)

    async def test_ciphertext_cannot_be_swapped_between_owners(self):
        await self.save(llm_api_key="key-a")
        await self.save(index=1, llm_api_key="key-b")
        async with self.sessions() as db:
            a, b = [await db.get(UserServiceSettings, u.id) for u in self.users]
            b.ciphertext = a.ciphertext
            await db.commit()
        response = await self.http.get("/api/v1/settings/services", headers=self.headers[1])
        self.assertEqual(response.status_code, 503)


class PrivateTransportTests(unittest.IsolatedAsyncioTestCase):
    def test_smtp_pins_public_address_preserves_tls_name_and_authenticates_after_tls(self):
        for port in (465, 587):
            events = []
            raw, wrapped = Mock(), Mock()
            tls = ssl.create_default_context()
            self.assertTrue(tls.check_hostname)
            self.assertEqual(tls.verify_mode, ssl.CERT_REQUIRED)
            def wrap(sock, *, server_hostname):
                self.assertIs(sock, raw)
                events.append(("tls", server_hostname))
                return wrapped
            class FakeSMTP:
                def __init__(self, host, port, timeout):
                    self.host = host
                    self.sock = self._get_socket(host, port, timeout)
                def starttls(self, *, context):
                    self.sock = context.wrap_socket(self.sock, server_hostname=self.host)
                def login(self, user, password):
                    self.assert_tls = self.sock is wrapped
                    if not self.assert_tls:
                        raise AssertionError("credentials sent before TLS")
                    events.append(("login", user, password))
                def __enter__(self): return self
                def __exit__(self, *args): self.sock.close()
            config = SimpleNamespace(SMTP_HOST="smtp.example.com", SMTP_PORT=port, SMTP_USERNAME="owner", SMTP_PASSWORD="fixture")
            with patch("app.core.private_clients.public_addresses", return_value=["93.184.215.14"]), \
                 patch("app.core.private_clients.socket.create_connection", return_value=raw) as connect, \
                 patch("app.core.private_clients.ssl.create_default_context", return_value=tls), \
                 patch.object(tls, "wrap_socket", side_effect=wrap), \
                 patch("app.core.private_clients.smtplib.SMTP", FakeSMTP), \
                 patch("app.core.private_clients.smtplib.SMTP_SSL", FakeSMTP):
                with smtp_connection(config): pass
            connect.assert_called_once_with(("93.184.215.14", port), 10)
            self.assertEqual(events, [("tls", "smtp.example.com"), ("login", "owner", "fixture")])
            wrapped.close.assert_called_once()

    async def test_dns_is_pinned_host_and_sni_preserved_without_buffering(self):
        seen = []
        async def send(request):
            seen.append((str(request.url), request.headers["host"], request.extensions["sni_hostname"]))
            return httpx.Response(200, stream=httpx.ByteStream(b"data: chunk\n\n"))
        transport = PublicModelTransport()
        original = transport.transport
        transport.transport = httpx.MockTransport(send)
        await original.aclose()
        async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
            with patch("app.core.private_clients.public_addresses", return_value=["93.184.215.14"]):
                response = await client.get("https://provider.example.com/v1/models")
        self.assertEqual(response.content, b"data: chunk\n\n")
        self.assertEqual(seen, [("https://93.184.215.14/v1/models", "provider.example.com", "provider.example.com")])

    async def test_dns_rebinding_to_private_ip_is_rejected_before_transport(self):
        transport = PublicModelTransport()
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaises(ValueError):
                await transport.handle_async_request(httpx.Request("POST", "https://provider.example.com/v1/chat/completions"))
        await transport.aclose()

    async def test_model_response_size_is_bounded(self):
        stream = BoundedStream(httpx.ByteStream(b"too large"), limit=2)
        with self.assertRaises(ValueError):
            async for _ in stream:
                pass
        await stream.aclose()
