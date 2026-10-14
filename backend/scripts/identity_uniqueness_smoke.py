"""Populated identity migration and real competing writers on disposable PostgreSQL."""
import argparse
import asyncio
import json
import tempfile
import uuid
from pathlib import Path

import asyncpg
from alembic import command
from alembic.config import Config

from scripts.postgres_recovery_smoke import administer, audit_url
from scripts.recovery_worker import configure


async def connect(url):
    return await asyncpg.connect(host=url.host, port=url.port or 5432, user=url.username,
                                 password=url.password, database=url.database, timeout=10)


async def execute(url, sql):
    connection = await connect(url)
    try:
        return await connection.fetch(sql)
    finally:
        await connection.close()


async def competing_updates(url, field, first_value, second_value):
    ready = asyncio.Event()
    count = 0

    async def writer(identifier, value):
        nonlocal count
        connection = await connect(url)
        try:
            count += 1
            if count == 2:
                ready.set()
            await asyncio.wait_for(ready.wait(), timeout=10)
            try:
                async with connection.transaction():
                    await connection.execute(f"UPDATE users SET {field} = $1 WHERE id = $2", value, identifier)
                return "committed"
            except asyncpg.UniqueViolationError:
                return "conflict"
        finally:
            await connection.close()

    outcomes = await asyncio.wait_for(asyncio.gather(writer("a", first_value), writer("b", second_value)), timeout=20)
    assert sorted(outcomes) == ["committed", "conflict"], outcomes
    return outcomes


async def actual_profile_conflict(url):
    from fastapi import HTTPException
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.api.auth import update_me
    from app.models.user import User
    from app.schemas.auth import UserUpdateRequest
    engine = create_async_engine(url.render_as_string(hide_password=False))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as db:
            user = await db.get(User, "b")
            try:
                await update_me(UserUpdateRequest(username="ALICE"), user, db)
            except HTTPException as error:
                assert error.status_code == 409
            else:
                raise AssertionError("Expected profile conflict")
            await db.rollback()
    finally:
        await engine.dispose()


def verify(database_url, output):
    root = audit_url(database_url)
    name = "infopulse_recovery_audit_" + uuid.uuid4().hex[:16]
    disposable = root.set(database=name)
    output.mkdir(parents=True, exist_ok=True)
    result = {"completed": False, "checks": []}
    created = False
    try:
        asyncio.run(administer(root, name, True))
        created = True
        with tempfile.TemporaryDirectory() as directory:
            configure(disposable.render_as_string(hide_password=False), directory)
            config = Config("alembic.ini")
            command.upgrade(config, "20261009_0033")
            seed = """INSERT INTO users(id, username, email, password_hash, is_active, is_admin, created_at, updated_at)
                VALUES ('a', 'Alice', 'alice@example.com', 'fixture-only', true, false, now(), now()),
                       ('b', 'ALICE', 'bob@example.com', 'fixture-only', true, false, now(), now())"""
            asyncio.run(execute(disposable, seed))
            snapshot = "SELECT id, username, email, password_hash, is_active, is_admin, created_at, updated_at FROM users ORDER BY id"
            for field, value in (("username", "ALICE"), ("email", "ALICE@EXAMPLE.COM")):
                asyncio.run(execute(disposable, "UPDATE users SET username='Bob', email='bob@example.com' WHERE id='b'"))
                asyncio.run(execute(disposable, f"UPDATE users SET {field}='{value}' WHERE id='b'"))
                before = asyncio.run(execute(disposable, snapshot))
                try:
                    command.upgrade(config, "head")
                except RuntimeError as error:
                    assert f"users.{field} collision" in str(error)
                else:
                    raise AssertionError("Migration accepted conflicting accounts")
                assert asyncio.run(execute(disposable, snapshot)) == before
                assert asyncio.run(execute(disposable, "SELECT version_num FROM alembic_version"))[0][0] == "20261009_0033"
                assert not asyncio.run(execute(disposable, "SELECT indexname FROM pg_indexes WHERE tablename='users' AND indexname LIKE 'uq_users_%_lower'"))
                result["checks"].append(f"legacy {field} conflict blocks migration without changing accounts, version or either index")
            asyncio.run(execute(disposable, "UPDATE users SET username='Bob', email='bob@example.com' WHERE id='b'"))
            before = asyncio.run(execute(disposable, snapshot))
            command.upgrade(config, "head")
            assert asyncio.run(execute(disposable, snapshot)) == before
            asyncio.run(actual_profile_conflict(disposable))
            result["checks"].append("actual profile endpoint rejects conflicting identity with 409 on migrated PostgreSQL")
            for field, values in (("username", ("SharedUser", "SHAREDUSER")), ("email", ("shared@example.com", "SHARED@EXAMPLE.COM"))):
                result[field + "_writers"] = asyncio.run(competing_updates(disposable, field, *values))
                asyncio.run(execute(disposable, "UPDATE users SET username=CASE id WHEN 'a' THEN 'Alice' ELSE 'Bob' END, email=CASE id WHEN 'a' THEN 'alice@example.com' ELSE 'bob@example.com' END"))
            result["checks"].append("independent concurrent username and email writers each yield one commit and one unique conflict")
            command.downgrade(config, "20261009_0033")
            assert asyncio.run(execute(disposable, snapshot)) == before
            command.upgrade(config, "head")
            assert asyncio.run(execute(disposable, snapshot)) == before
            result["checks"].append("populated head -> 33 -> head round trip preserves every identity field")
            result["completed"] = True
            result["scope"] = "PostgreSQL database lower() identity semantics; ASCII case variants exercised; no provider, Unicode collation or account deletion claim"
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        try:
            if created:
                asyncio.run(administer(root, name, False))
        finally:
            (output / "identity-uniqueness.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default="postgresql+asyncpg://audit:audit-local-only@127.0.0.1:15432/infopulse_audit")
    parser.add_argument("--output", type=Path, default=Path("../acceptance-artifacts/identity"))
    args = parser.parse_args()
    verify(args.database_url, args.output)
