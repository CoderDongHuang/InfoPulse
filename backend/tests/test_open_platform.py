import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.api.platform import api_key_identity, create_key, create_oauth_app, create_webhook, install, replay, review_installation
from app.core.database import Base
from app.models.platform import DeveloperAPIKey, OAuthApplication, WebhookDelivery
from app.models.user import User
from app.schemas.platform import APIKeyCreate, ConnectorInstall, OAuthAppCreate, ReviewDecision, WebhookCreate
from app.services.enterprise import provision_personal_tenant, resolve_tenant
from app.services.platform import hash_secret, pkce_s256, sign_webhook, verify_webhook


class OpenPlatformTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection: await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self): await self.engine.dispose()

    async def tenant(self, db):
        user = User(username="owner", email="owner@platform.test", password_hash="x"); db.add(user); await db.flush()
        org = await provision_personal_tenant(db, user); await db.flush()
        return user, org, await resolve_tenant(db, user, org.id, None)

    async def test_api_key_is_hashed_and_scope_is_enforced(self):
        async with self.sessions() as db:
            user, org, ctx = await self.tenant(db)
            response = await create_key(APIKeyCreate(name="Automation", scopes=["events:read"]), ctx, user, db)
            row = await db.get(DeveloperAPIKey, response["id"])
            self.assertEqual(row.key_hash, hash_secret(response["secret"])); self.assertNotIn(response["secret"], row.key_hash)
            identity = await api_key_identity(SimpleNamespace(credentials=response["secret"]), "events:read", db)
            self.assertEqual(identity["organization_id"], org.id)
            with self.assertRaises(HTTPException) as raised: await api_key_identity(SimpleNamespace(credentials=response["secret"]), "reports:write", db)
            self.assertEqual(raised.exception.status_code, 403)

    async def test_oauth_apps_require_review_and_pkce_is_s256(self):
        async with self.sessions() as db:
            user, org, ctx = await self.tenant(db)
            result = await create_oauth_app(OAuthAppCreate(name="Public client", redirect_uris=["https://client.example/callback"], scopes=["events:read"]), ctx, user, db)
            app = await db.get(OAuthApplication, result["id"])
            self.assertEqual(app.review_status, "pending"); self.assertEqual(app.client_secret_hash, "")
            self.assertEqual(pkce_s256("a" * 43), "ZtNPunH49FD35FWYhT5Tv8I7vRKQJ8uxMaL0_9eHjNA")

    async def test_signature_detects_payload_tampering(self):
        body = b'{"id":"evt_1"}'; signature = sign_webhook("secret", "123", "evt_1", body)
        self.assertTrue(verify_webhook("secret", "123", "evt_1", body, "sha256=" + signature))
        self.assertFalse(verify_webhook("secret", "123", "evt_1", b"{}", "sha256=" + signature))

    async def test_replay_creates_linked_attempt(self):
        async with self.sessions() as db:
            user, org, ctx = await self.tenant(db)
            from app.models.platform import WebhookEndpoint
            endpoint = WebhookEndpoint(organization_id=org.id, name="Events", target_url="https://example.com/hook", event_types=["event.created"], secret_hash="x", secret_ciphertext="x")
            db.add(endpoint); await db.flush()
            original = WebhookDelivery(organization_id=org.id, endpoint_id=endpoint.id, event_id="evt", event_type="event.created", fingerprint="f", payload={"id": "evt"}, status="failed")
            db.add(original); await db.flush()
            result = await replay(original.id, ctx, db)
            self.assertEqual(result["attempt"], 2); self.assertEqual(result["replay_of_id"], original.id)

    async def test_write_connector_requires_admin_review_and_revocation_clears_secret_reference(self):
        async with self.sessions() as db:
            user, _org, ctx = await self.tenant(db)
            result = await install(ConnectorInstall(connector_key="slack", credential_reference="vault://tenant/slack"), ctx, user, db)
            self.assertEqual(result["status"], "pending")
            await review_installation(result["id"], ReviewDecision(decision="approved"), ctx, user, db)
            from app.models.platform import ConnectorInstallation
            row = await db.get(ConnectorInstallation, result["id"]); self.assertEqual(row.status, "approved")


if __name__ == "__main__": unittest.main()
