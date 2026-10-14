"""Legacy email-shaped usernames must not shadow another user's email login."""
import unittest

import httpx
from fastapi import FastAPI

from app.api.auth import router
from app.core.database import get_db
from app.core.security import hash_password, verify_token
from app.models.user import User
from tests import test_auth_transactions


class LoginIdentityTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_auth_transactions.AuthTransactionTests.asyncSetUp
    asyncTearDown = test_auth_transactions.AuthTransactionTests.asyncTearDown

    async def test_email_login_cannot_be_shadowed_by_legacy_username(self):
        async with self.sessions() as db:
            owner = await db.get(User, self.user.id)
            owner.password_hash = hash_password("owner-secret")
            legacy = User(username=owner.email.upper(), email="legacy@example.com",
                          password_hash=hash_password("legacy-secret"))
            db.add(legacy)
            await db.commit()
            legacy_id = legacy.id

        app = FastAPI()
        app.include_router(router)

        async def session_override():
            async with self.sessions() as db:
                yield db

        app.dependency_overrides[get_db] = session_override
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            for account, password, expected in (
                (self.user.email.upper(), "owner-secret", self.user.id),
                (self.user.username.upper(), "owner-secret", self.user.id),
                ("LEGACY@EXAMPLE.COM", "legacy-secret", legacy_id),
                (self.user.email, "legacy-secret", None),
                ("missing@example.com", "owner-secret", None),
                ("missing-user", "owner-secret", None),
            ):
                with self.subTest(account=account, expected=expected):
                    response = await client.post("/api/v1/auth/login", json={"username": "  " + account + "  ", "password": password})
                    self.assertEqual(response.status_code, 200 if expected else 401, response.text)
                    if expected:
                        for key in ("access_token", "refresh_token"):
                            self.assertEqual(verify_token(response.json()[key])["sub"], expected)
                    else:
                        self.assertNotIn("access_token", response.json())
