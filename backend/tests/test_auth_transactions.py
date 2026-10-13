"""Authentication revocation must be durable before the success response."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.api.auth import logout, refresh
from app.core.database import Base
from app.core.security import create_access_token, create_refresh_token
from app.dependencies import get_current_user
from app.models.auth_session import AuthSession
from app.models.user import User
from app.schemas.workflows import RefreshTokenRequest


class AuthTransactionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine("sqlite+aiosqlite:///" + str(Path(self.tmp.name) / "audit.db"))
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.sessions() as db:
            self.user = User(username="auth-tx", email="auth-tx@example.com", password_hash="x")
            db.add(self.user)
            await db.flush()
            db.add(AuthSession(id="revocation-session", user_id=self.user.id, refresh_jti="single-use-refresh", expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
            await db.commit()
        payload = {"sub": self.user.id, "username": self.user.username, "sid": "revocation-session"}
        self.credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=create_access_token(payload))
        self.refresh_token = create_refresh_token({**payload, "jti": "single-use-refresh"})

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.tmp.cleanup()

    async def test_logout_immediately_denies_access_and_refresh_on_other_connections(self):
        async with self.sessions() as writer:
            async with self.sessions() as reader:
                self.assertEqual((await get_current_user(self.credentials, reader)).id, self.user.id)
            await logout(self.user, self.credentials, writer)
            # No dependency finalizer or test-side commit: the writer remains open.
            async with self.sessions() as reader:
                with self.assertRaises(HTTPException) as error:
                    await get_current_user(self.credentials, reader)
                self.assertEqual(error.exception.status_code, 401)
            async with self.sessions() as reader:
                with self.assertRaises(HTTPException) as error:
                    await refresh(RefreshTokenRequest(refresh_token=self.refresh_token), reader)
                self.assertEqual(error.exception.status_code, 401)

    async def test_logout_commit_failure_cannot_return_success(self):
        async with self.sessions() as writer:
            with patch.object(writer, "commit", AsyncMock(side_effect=RuntimeError("commit rejected"))):
                with self.assertRaisesRegex(RuntimeError, "commit rejected"):
                    await logout(self.user, self.credentials, writer)
            await writer.rollback()
            async with self.sessions() as reader:
                self.assertIsNone((await reader.get(AuthSession, "revocation-session")).revoked_at)
