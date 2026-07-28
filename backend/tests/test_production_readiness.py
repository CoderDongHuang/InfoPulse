import unittest
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.config import Settings
from app.core.database import Base
from app.core.observability import metrics, redact
from app.core.security import hash_password
from app.dependencies import require_admin
from app.models.intelligence import AuditLog, BIQueryHistory, ModelUsage
from app.models.user import User
from app.schemas.auth import AccountDeleteRequest
from app.api.auth import delete_me
from app.services.retention import apply_retention


class ProductionConfigurationTests(unittest.TestCase):
    def test_production_rejects_defaults(self):
        settings = Settings(ENVIRONMENT="production", DATABASE_URL="sqlite+aiosqlite:///unsafe.db")
        errors = " ".join(settings.production_errors())
        self.assertIn("JWT_SECRET_KEY", errors)
        self.assertIn("PostgreSQL", errors)
        self.assertIn("ADMIN_EMAILS", errors)

    def test_production_accepts_explicit_security_configuration(self):
        settings = Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://app:password@db/infopulse",
            JWT_SECRET_KEY="x" * 48,
            ADMIN_EMAILS=["admin@example.com"],
            METRICS_TOKEN="m" * 32,
            CORS_ORIGINS=["https://app.example.com"],
            TRUSTED_HOSTS=["api.example.com"],
        )
        self.assertEqual(settings.production_errors(), [])

    def test_redaction_removes_common_secret_shapes(self):
        value = redact("Authorization: Bearer abc.def token=secret password='open-sesame'")
        self.assertNotIn("abc.def", value)
        self.assertNotIn("open-sesame", value)
        self.assertGreaterEqual(value.count("[REDACTED]"), 2)

    def test_metrics_never_include_request_values(self):
        metrics.begin()
        metrics.finish("GET", "/api/v1/search", 200, .01)
        rendered = metrics.render()
        self.assertIn('route="/api/v1/search"', rendered)
        self.assertNotIn("query=", rendered)


class AuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_admin_cannot_use_admin_dependency(self):
        with self.assertRaises(HTTPException) as raised:
            await require_admin(User(username="member", email="member@example.com", password_hash="x"))
        self.assertEqual(raised.exception.status_code, 403)

    async def test_admin_dependency_accepts_admin(self):
        user = User(username="admin", email="admin@example.com", password_hash="x", is_admin=True)
        self.assertIs(await require_admin(user), user)


class PrivacyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_account_delete_requires_password_and_removes_user(self):
        async with self.sessions() as db:
            user = User(username="delete-me", email="delete@example.com", password_hash=hash_password("secret1"))
            db.add(user)
            await db.commit()
            await delete_me(AccountDeleteRequest(password="secret1", confirmation="DELETE"), user, db)
            await db.commit()
            self.assertIsNone(await db.get(User, user.id))

    async def test_retention_deletes_only_expired_operational_records(self):
        now = datetime.now(timezone.utc)
        async with self.sessions() as db:
            user = User(username="retention", email="retention@example.com", password_hash="x")
            db.add(user)
            await db.flush()
            old = now - timedelta(days=400)
            db.add_all([
                AuditLog(user_id=user.id, action="old", target_type="test", target_id="1", created_at=old),
                BIQueryHistory(user_id=user.id, question="old", query_plan={}, result={}, created_at=old),
                ModelUsage(user_id=user.id, feature="test", model_name="test", created_at=now),
            ])
            await db.commit()
            result = await apply_retention(db, 365, now)
            self.assertEqual(result["audit_logs"], 1)
            self.assertEqual(result["bi_queries"], 1)
            self.assertEqual(result["model_usage"], 0)
