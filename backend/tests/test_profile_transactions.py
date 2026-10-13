"""Profile updates must be durable before the endpoint returns success."""
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.api.auth import update_me
from app.dependencies import get_current_user
from app.models.auth_session import AuthSession
from app.models.user import User
from app.schemas.auth import UserUpdateRequest
from app.services.auth_service import update_user
from tests import test_auth_transactions


class ProfileTransactionTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_auth_transactions.AuthTransactionTests.asyncSetUp
    asyncTearDown = test_auth_transactions.AuthTransactionTests.asyncTearDown

    async def test_update_visible_on_another_connection_before_writer_closes(self):
        async with self.sessions() as writer:
            user = await writer.get(User, self.user.id)
            profile = await update_me(UserUpdateRequest(username="new-name", email="new@example.com", avatar_url="/avatar.png"), user, writer)
            self.assertEqual(profile.username, "new-name")
            # No test commit or dependency finalizer; writer is still open.
            async with self.sessions() as reader:
                persisted = await get_current_user(self.credentials, reader)
                self.assertEqual(persisted.username, profile.username)
                self.assertEqual(persisted.email, profile.email)
                self.assertEqual(persisted.avatar_url, profile.avatar_url)
                self.assertFalse(persisted.is_admin)
                self.assertTrue(persisted.is_active)
                self.assertEqual((await reader.get(AuthSession, "revocation-session")).refresh_jti, "single-use-refresh")

    async def test_commit_failure_cannot_return_profile_or_persist_changes(self):
        async with self.sessions() as writer:
            user = await writer.get(User, self.user.id)
            with patch.object(writer, "commit", AsyncMock(side_effect=RuntimeError("commit rejected"))):
                with self.assertRaisesRegex(RuntimeError, "commit rejected"):
                    await update_me(UserUpdateRequest(username="never-published", email="never@example.com", avatar_url="/never.png"), user, writer)
            await writer.rollback()
            async with self.sessions() as reader:
                persisted = await get_current_user(self.credentials, reader)
                self.assertEqual(persisted.username, self.user.username)
                self.assertEqual(persisted.email, self.user.email)
                self.assertEqual(persisted.avatar_url, "")

    async def test_missing_user_remains_404_without_commit(self):
        async with self.sessions() as writer:
            missing = User(id="does-not-exist", username="missing", email="missing@example.com", password_hash="x")
            with patch.object(writer, "commit", AsyncMock()) as commit:
                with self.assertRaises(HTTPException) as error:
                    await update_me(UserUpdateRequest(username="updated"), missing, writer)
                self.assertEqual(error.exception.status_code, 404)
                commit.assert_not_awaited()

    async def test_service_stays_composable_and_does_not_commit(self):
        async with self.sessions() as writer:
            with patch.object(writer, "commit", AsyncMock()) as commit:
                profile = await update_user(writer, self.user.id, UserUpdateRequest(username="transaction-local"))
                self.assertEqual(profile.username, "transaction-local")
                commit.assert_not_awaited()
            async with self.sessions() as reader:
                self.assertEqual((await reader.get(User, self.user.id)).username, self.user.username)
            await writer.rollback()
