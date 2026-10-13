"""Recovery acceptance tools must reject business databases before mutating anything."""
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.postgres_recovery_smoke import administer, audit_url
from scripts.recovery_worker import configure


class RecoveryHarnessTests(unittest.IsolatedAsyncioTestCase):
    def test_only_explicit_local_audit_server_is_accepted(self):
        self.assertEqual(audit_url("postgresql+asyncpg://audit:fixture@127.0.0.1:15432/infopulse_audit").database, "infopulse_audit")
        for value in ("postgresql+asyncpg://audit:fixture@db/infopulse_audit",
                      "postgresql+asyncpg://audit:fixture@127.0.0.1/business",
                      "postgresql+asyncpg://app:fixture@127.0.0.1/infopulse_audit",
                      "sqlite+aiosqlite:///audit.db"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                audit_url(value)

    def test_worker_rejects_non_disposable_database_before_config_changes(self):
        with patch.dict("os.environ", {"LLM_API_KEY": "do-not-read"}, clear=True):
            with self.assertRaises(ValueError):
                configure("postgresql+asyncpg://audit:fixture@127.0.0.1/business", Path("unused"))
            import os
            self.assertEqual(os.environ["LLM_API_KEY"], "do-not-read")

    async def test_database_ddl_requires_generated_name_before_connecting(self):
        for name in ("infopulse_audit", "business", 'audit"; DROP DATABASE business; --'):
            with patch("scripts.postgres_recovery_smoke.asyncpg.connect") as connect:
                with self.assertRaises(ValueError):
                    await administer(audit_url("postgresql+asyncpg://audit:fixture@127.0.0.1/infopulse_audit"), name, False)
                connect.assert_not_called()
