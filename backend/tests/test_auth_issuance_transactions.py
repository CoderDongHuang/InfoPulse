"""Issue credentials only after their database transaction is durable."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func, select

from app.api.auth import login, refresh, register, sso_exchange
from app.core.security import hash_password, verify_token
from app.dependencies import get_current_user
from app.models.auth_session import AuthSession
from app.models.enterprise import IdentityProvider, OrganizationMember, WorkspaceMember
from app.models.user import User
from app.schemas.auth import UserLoginRequest, UserRegisterRequest
from app.schemas.workflows import RefreshTokenRequest
from app.services.enterprise import provision_personal_tenant
from tests import test_auth_transactions


class AuthIssuanceTransactionTests(unittest.IsolatedAsyncioTestCase):
    asyncTearDown = test_auth_transactions.AuthTransactionTests.asyncTearDown

    async def asyncSetUp(self):
        await test_auth_transactions.AuthTransactionTests.asyncSetUp(self)
        async with self.sessions() as db:
            user = await db.get(User, self.user.id)
            user.password_hash = hash_password("audit-secret-123")
            org = await provision_personal_tenant(db, user)
            self.org_id, self.org_slug = org.id, org.slug
            db.add(IdentityProvider(organization_id=org.id, provider_type="oidc", name="Test broker", enabled=True))
            await db.commit()

    async def issue(self, operation, db):
        if operation == "register":
            return await register(UserRegisterRequest(username="registered", email="registered@example.com", password="audit-secret-123"), db)
        if operation == "login":
            return await login(UserLoginRequest(username=self.user.username, password="audit-secret-123"), db)
        if operation == "sso":
            with patch("app.config.get_settings", return_value=SimpleNamespace(SSO_PROXY_SECRET="s" * 48)):
                return await sso_exchange("s" * 48, self.org_slug, "sso-new@example.com", "verified-subject", db)
        if operation == "refresh":
            return await refresh(RefreshTokenRequest(refresh_token=self.refresh_token), db)
        raise AssertionError(operation)

    async def assert_immediately_visible(self, operation):
        async with self.sessions() as writer:
            tokens = await self.issue(operation, writer)
            # Deliberately keep writer open; no dependency cleanup or test commit.
            async with self.sessions() as reader:
                user = await get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=tokens.access_token), reader)
                payload = verify_token(tokens.refresh_token)
                session = await reader.get(AuthSession, payload["sid"])
                self.assertEqual(session.refresh_jti, payload["jti"])
                self.assertEqual(session.user_id, user.id)
                self.assertFalse(user.is_admin)
                if operation in ("register", "sso"):
                    membership = await reader.scalar(select(OrganizationMember).where(OrganizationMember.user_id == user.id))
                    self.assertIsNotNone(membership)
                    self.assertEqual(membership.role_key, "owner" if operation == "register" else "member")
                    if operation == "register":
                        self.assertIsNotNone(await reader.scalar(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)))
                    else:
                        self.assertEqual(membership.organization_id, self.org_id)
            # The issued refresh token must work immediately on another connection.
            async with self.sessions() as reader:
                replacement = await refresh(RefreshTokenRequest(refresh_token=tokens.refresh_token), reader)
                self.assertTrue(replacement.access_token)
            async with self.sessions() as reader:
                with self.assertRaises(HTTPException) as error:
                    await refresh(RefreshTokenRequest(refresh_token=tokens.refresh_token), reader)
                self.assertEqual(error.exception.status_code, 401)
            if operation == "refresh":
                async with self.sessions() as reader:
                    with self.assertRaises(HTTPException) as error:
                        await self.issue("refresh", reader)
                    self.assertEqual(error.exception.status_code, 401)

    async def assert_failed_commit(self, operation):
        async with self.sessions() as writer:
            with patch.object(writer, "commit", AsyncMock(side_effect=RuntimeError("commit rejected"))):
                with self.assertRaisesRegex(RuntimeError, "commit rejected"):
                    await self.issue(operation, writer)
            await writer.rollback()
            async with self.sessions() as reader:
                self.assertEqual(await reader.scalar(select(func.count()).select_from(AuthSession)), 1)
                self.assertEqual(await reader.scalar(select(func.count()).select_from(User)), 1)
                self.assertEqual(await reader.scalar(select(func.count()).select_from(OrganizationMember)), 1)
                session = await reader.get(AuthSession, "revocation-session")
                self.assertEqual(session.refresh_jti, "single-use-refresh")
                self.assertIsNone(session.revoked_at)

    async def test_register_commits_identity_tenant_and_session(self):
        await self.assert_immediately_visible("register")

    async def test_login_commits_session(self):
        await self.assert_immediately_visible("login")

    async def test_sso_commits_identity_membership_and_session(self):
        await self.assert_immediately_visible("sso")

    async def test_refresh_commits_rotation_before_return(self):
        await self.assert_immediately_visible("refresh")

    async def test_register_commit_failure_returns_no_credentials(self):
        await self.assert_failed_commit("register")

    async def test_login_commit_failure_returns_no_credentials(self):
        await self.assert_failed_commit("login")

    async def test_sso_commit_failure_returns_no_credentials(self):
        await self.assert_failed_commit("sso")

    async def test_refresh_commit_failure_preserves_old_jti(self):
        await self.assert_failed_commit("refresh")
