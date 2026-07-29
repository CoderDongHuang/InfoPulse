import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.api.enterprise import create_role, decide_approval
from app.api.auth import sso_exchange
from app.core.database import Base
from app.models.enterprise import ApprovalRequest, IdentityProvider, OrganizationMember
from app.models.user import User
from app.schemas.enterprise import ApprovalDecision, RoleCreate
from app.services.enterprise import hash_scim_token, new_scim_token, provision_personal_tenant, resolve_tenant


class EnterpriseGovernanceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def users(self, db):
        owner = User(username="owner", email="owner@example.com", password_hash="x")
        member = User(username="member", email="member@example.com", password_hash="x")
        outsider = User(username="outsider", email="outsider@example.com", password_hash="x")
        db.add_all([owner, member, outsider]); await db.flush()
        org = await provision_personal_tenant(db, owner)
        db.add(OrganizationMember(organization_id=org.id, user_id=member.id, role_key="member"))
        await db.flush()
        return owner, member, outsider, org

    async def test_tenant_resolution_rejects_outsider(self):
        async with self.sessions() as db:
            owner, _member, outsider, org = await self.users(db)
            context = await resolve_tenant(db, owner, org.id, None)
            self.assertEqual(context.organization.id, org.id)
            with self.assertRaises(HTTPException) as raised:
                await resolve_tenant(db, outsider, org.id, None)
            self.assertEqual(raised.exception.status_code, 403)

    async def test_member_cannot_create_custom_role(self):
        async with self.sessions() as db:
            _owner, member, _outsider, org = await self.users(db)
            context = await resolve_tenant(db, member, org.id, None)
            with self.assertRaises(HTTPException) as raised:
                await create_role(RoleCreate(key="reviewer", name="Reviewer", permissions=["org.read"]), context, member, db)
            self.assertEqual(raised.exception.status_code, 403)

    async def test_requester_cannot_approve_own_request(self):
        async with self.sessions() as db:
            owner, _member, _outsider, org = await self.users(db)
            context = await resolve_tenant(db, owner, org.id, None)
            request = ApprovalRequest(organization_id=org.id, requested_by=owner.id, action_type="bulk_export", risk_level="high", payload={})
            db.add(request); await db.flush()
            with self.assertRaises(HTTPException) as raised:
                await decide_approval(request.id, ApprovalDecision(decision="approved", note="Reviewed evidence"), context, owner, db)
            self.assertEqual(raised.exception.status_code, 409)

    async def test_scim_token_is_stored_only_as_hash(self):
        async with self.sessions() as db:
            owner, _member, _outsider, org = await self.users(db)
            token, token_hash = new_scim_token()
            provider = IdentityProvider(organization_id=org.id, provider_type="scim", name="Directory", enabled=True, scim_token_hash=token_hash)
            db.add(provider); await db.flush()
            stored = await db.scalar(select(IdentityProvider.scim_token_hash).where(IdentityProvider.id == provider.id))
            self.assertEqual(stored, hash_scim_token(token))
            self.assertNotEqual(stored, token)

    async def test_verified_sso_proxy_can_provision_member(self):
        async with self.sessions() as db:
            owner, _member, _outsider, org = await self.users(db)
            db.add(IdentityProvider(organization_id=org.id, provider_type="oidc", name="Corporate OIDC", enabled=True))
            await db.flush()
            with patch("app.config.get_settings", return_value=SimpleNamespace(SSO_PROXY_SECRET="s" * 48)):
                tokens = await sso_exchange("s" * 48, org.slug, "new.user@example.com", "oidc-subject-1", db)
            self.assertTrue(tokens.access_token)
            new_user = await db.scalar(select(User).where(User.email == "new.user@example.com"))
            membership = await db.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == org.id, OrganizationMember.user_id == new_user.id))
            self.assertEqual(membership.role_key, "member")
