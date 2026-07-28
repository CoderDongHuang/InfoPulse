"""Authentication validation and token-boundary tests."""

import unittest

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError

from app.core.security import create_refresh_token
from app.dependencies import get_current_user
from app.schemas.auth import UserLoginRequest, UserRegisterRequest


class AuthSchemaTests(unittest.TestCase):
    def test_registration_normalizes_account_fields(self):
        payload = UserRegisterRequest(
            username="  Alice  ", email="ALICE@Example.com", password="secret1"
        )
        self.assertEqual(payload.username, "Alice")
        self.assertEqual(str(payload.email), "alice@example.com")

    def test_registration_rejects_invalid_email(self):
        with self.assertRaises(ValidationError):
            UserRegisterRequest(username="alice", email="not-an-email", password="secret1")

    def test_login_trims_account(self):
        payload = UserLoginRequest(username="  alice@example.com ", password="secret1")
        self.assertEqual(payload.username, "alice@example.com")


class AuthTokenTests(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_token_cannot_access_protected_endpoint(self):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=create_refresh_token({"sub": "user-1"})
        )
        with self.assertRaises(HTTPException) as raised:
            await get_current_user(credentials=credentials, db=None)
        self.assertEqual(raised.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
