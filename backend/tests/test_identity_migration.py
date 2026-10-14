"""Exercise the actual Alembic revision on populated SQLite tables."""
import unittest

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError


class IdentityMigrationTests(unittest.TestCase):
    def setUp(self):
        import importlib.util
        from pathlib import Path
        path = Path(__file__).resolve().parents[1] / "alembic/versions/20261014_0034_identity_uniqueness.py"
        spec = importlib.util.spec_from_file_location("identity_revision", path)
        self.revision = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.revision)
        self.engine = create_engine("sqlite:///:memory:")
        self.connection = self.engine.connect()
        self.connection.execute(text("CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, email TEXT NOT NULL UNIQUE)"))
        self.connection.execute(text("INSERT INTO users VALUES ('a', 'Alice', 'alice@example.com'), ('b', 'Bob', 'bob@example.com')"))
        self.operations = Operations(MigrationContext.configure(self.connection))

    def tearDown(self):
        self.connection.close()
        self.engine.dispose()

    def run_revision(self, name):
        with Operations.context(self.operations.migration_context):
            getattr(self.revision, name)()

    def rows(self):
        return self.connection.execute(text("SELECT * FROM users ORDER BY id")).all()

    def test_round_trip_preserves_rows_and_reinstates_constraints(self):
        before = self.rows()
        self.run_revision("upgrade")
        self.assertEqual(before, self.rows())
        for sql in ("UPDATE users SET username = 'ALICE' WHERE id = 'b'",
                    "UPDATE users SET email = 'ALICE@EXAMPLE.COM' WHERE id = 'b'"):
            with self.assertRaises(IntegrityError):
                self.connection.execute(text(sql))
        self.run_revision("downgrade")
        self.assertEqual(before, self.rows())
        self.connection.execute(text("UPDATE users SET username = 'ALICE' WHERE id = 'b'"))
        with self.assertRaisesRegex(RuntimeError, "users.username collision"):
            self.run_revision("upgrade")
        self.connection.execute(text("UPDATE users SET username = 'Bob' WHERE id = 'b'"))
        self.run_revision("upgrade")
        self.assertEqual(before, self.rows())

    def test_legacy_conflicts_abort_before_either_index_and_preserve_accounts(self):
        for field, value in (("username", "ALICE"), ("email", "ALICE@EXAMPLE.COM")):
            with self.subTest(field=field):
                self.connection.execute(text(f"UPDATE users SET {field} = :value WHERE id = 'b'"), {"value": value})
                before = self.rows()
                with self.assertRaisesRegex(RuntimeError, f"users.{field} collision"):
                    self.run_revision("upgrade")
                self.assertEqual(before, self.rows())
                indexes = self.connection.execute(text("SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'uq_users_%_lower' ")).all()
                self.assertEqual(indexes, [])
                self.connection.execute(text("UPDATE users SET username = 'Bob', email = 'bob@example.com' WHERE id = 'b'"))
