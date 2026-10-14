"""Profile input and conflict checks through the real ASGI route and database."""
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.api.auth import router
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import UserRegisterRequest, UserUpdateRequest
from app.services.auth_service import register_user
from tests import test_auth_transactions


class ProfileSchemaTests(unittest.TestCase):
    def test_omitted_fields_are_not_written(self):
        self.assertEqual(UserUpdateRequest().model_dump(exclude_unset=True), {})
        schema = UserUpdateRequest.model_json_schema()
        self.assertNotIn("required", schema)
        for field in schema["properties"].values():
            self.assertEqual(field["type"], "string")
            self.assertNotIn("default", field)

    def test_null_is_rejected_for_every_profile_field(self):
        for key in ("username", "email", "avatar_url"):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                UserUpdateRequest(**{key: None})

    def test_normalization_and_avatar_clear(self):
        data = UserUpdateRequest(username="  Alice  ", email="ALICE@Example.com", avatar_url="")
        self.assertEqual(data.model_dump(exclude_unset=True),
                         {"username": "Alice", "email": "alice@example.com", "avatar_url": ""})

    def test_invalid_identity_inputs(self):
        for username in ("   ", " a ", " aa ", "abc@def", "a" * 51, 42):
            for schema in (UserUpdateRequest, UserRegisterRequest):
                fields = {"username": username}
                if schema is UserRegisterRequest:
                    fields.update(email="alice@example.com", password="secret1")
                with self.subTest(username=username, schema=schema), self.assertRaises(ValidationError):
                    schema(**fields)
        for email in ("", "not-an-email", "a@", "a@b", "a" * 90 + "@example.com"):
            with self.subTest(email=email), self.assertRaises(ValidationError):
                UserUpdateRequest(email=email)


class ProfileHTTPTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_auth_transactions.AuthTransactionTests.asyncSetUp
    asyncTearDown = test_auth_transactions.AuthTransactionTests.asyncTearDown

    def client(self, writer):
        app = FastAPI()
        app.include_router(router)

        async def session_override():
            # Deliberately no dependency commit: successful durability belongs to API.
            yield writer

        app.dependency_overrides[get_db] = session_override
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver",
                                headers={"Authorization": "Bearer " + self.credentials.credentials})

    async def test_invalid_payloads_return_422_and_leave_profile_unchanged(self):
        async with self.sessions() as writer, self.client(writer) as client:
            for payload in ({"username": None}, {"email": None}, {"avatar_url": None},
                            {"username": " a "}, {"username": "alice@example.com"}, {"email": "bad"}):
                response = await client.put("/api/v1/auth/me", json=payload)
                self.assertEqual(response.status_code, 422, response.text)
            async with self.sessions() as reader:
                original = await reader.get(User, self.user.id)
                self.assertEqual(original.username, self.user.username)
                self.assertEqual(original.email, self.user.email)

    async def test_case_insensitive_conflicts_return_409_without_partial_write(self):
        async with self.sessions() as db:
            db.add_all([User(username="OtherUser", email="other@example.com", password_hash="x"),
                        User(username="ThirdUser", email="third@example.com", password_hash="x")])
            await db.commit()
        async with self.sessions() as writer, self.client(writer) as client:
            for payload in ({"username": "OTHERUSER"}, {"email": "OTHER@EXAMPLE.COM"},
                            {"username": "OtherUser", "email": "THIRD@EXAMPLE.COM", "avatar_url": "/lost.png"}):
                response = await client.put("/api/v1/auth/me", json=payload)
                self.assertEqual(response.status_code, 409, response.text)
                async with self.sessions() as reader:
                    original = await reader.get(User, self.user.id)
                    self.assertEqual(original.username, self.user.username)
                    self.assertEqual(original.email, self.user.email)
                    self.assertEqual(original.avatar_url, "")
            # Two different existing identities must not raise MultipleResultsFound.
            with self.assertRaisesRegex(ValueError, "已被注册"):
                await register_user(writer, UserRegisterRequest(username="otheruser", email="third@example.com", password="secret1"))

    async def test_own_identity_empty_patch_and_normalized_update_are_durable(self):
        async with self.sessions() as writer, self.client(writer) as client:
            for payload in ({}, {"username": self.user.username.upper(), "email": self.user.email.upper()},
                            {"username": "  Alice  ", "email": "ALICE@Example.com", "avatar_url": "/avatar.png"},
                            {"avatar_url": ""}):
                response = await client.put("/api/v1/auth/me", json=payload)
                self.assertEqual(response.status_code, 200, response.text)
                async with self.sessions() as reader:
                    stored = await reader.get(User, self.user.id)
                    for field in ("username", "email", "avatar_url"):
                        self.assertEqual(getattr(stored, field), response.json()[field])
            self.assertEqual(response.json()["username"], "Alice")
            self.assertEqual(response.json()["email"], "alice@example.com")
            self.assertEqual(response.json()["avatar_url"], "")

    async def test_database_race_maps_to_conflict_and_rolls_back(self):
        async with self.sessions() as writer, self.client(writer) as client:
            failure = IntegrityError("UPDATE users", {}, Exception("unique constraint"))
            with patch.object(writer, "flush", AsyncMock(side_effect=failure)), patch.object(writer, "commit", AsyncMock()) as commit:
                response = await client.put("/api/v1/auth/me", json={"username": "race-loser"})
                self.assertEqual(response.status_code, 409, response.text)
                commit.assert_not_awaited()
            async with self.sessions() as reader:
                self.assertEqual((await reader.get(User, self.user.id)).username, self.user.username)
