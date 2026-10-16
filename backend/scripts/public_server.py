"""Run the real, key-free localhost application with persistent unique secrets.

Never reads .env or reuses audit fixtures. Data is stored in .public-local.
This is a single-host self-hosting entrypoint, not an Internet deployment recipe.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import secrets

from alembic import command
from alembic.config import Config
import uvicorn
from app.config import Settings


def configure(root: Path):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / "runtime.json"
    if not path.exists():
        values = {name: secrets.token_urlsafe(48) for name in (
            "JWT_SECRET_KEY", "PLATFORM_ENCRYPTION_KEY", "METRICS_TOKEN", "SSO_PROXY_SECRET")}
        try:
            with path.open("x", encoding="utf-8") as stream:
                json.dump(values, stream)
            path.chmod(0o600)
        except FileExistsError:
            pass
    values = json.loads(path.read_text(encoding="utf-8"))
    if any(len(values.get(name, "")) < 32 for name in ("JWT_SECRET_KEY", "PLATFORM_ENCRYPTION_KEY")):
        raise ValueError("Local secret configuration is invalid; restore the original runtime.json")
    Settings.model_config["env_file"] = None
    for key in Settings.model_fields:
        os.environ.pop(key, None)
    os.environ.update({**values,
        "DATABASE_URL": "sqlite+aiosqlite:///" + (root / "infopulse.db").as_posix(),
        "KNOWLEDGE_STORAGE_PATH": str(root / "knowledge"),
        "REDIS_URL": "redis://127.0.0.1:16379/1",
        "CORS_ORIGINS": '["http://127.0.0.1:15174","http://localhost:5173","http://127.0.0.1:5173"]',
        "ADMIN_EMAILS": "[]",
        "CRAWLER_ENABLED": "false", "MEDIA_WORKER_ENABLED": "false",
        "SOURCE_SYNC_ENABLED": "true", "TASK_SCHEDULER_ENABLED": "true",
        "DEMO_MODE": "false",
    })
    from app.config import get_settings
    get_settings.cache_clear()


async def sync_once():
    from app.core.database import _get_sessionmaker, close_db
    from app.models.intelligence import DataSource
    from app.services.source_sync import ensure_builtin_sources, sync_source
    from sqlalchemy import select
    sessions = _get_sessionmaker()
    try:
        async with sessions() as db:
            await ensure_builtin_sources(db)
            await db.commit()
            ids = list((await db.scalars(select(DataSource.id).where(DataSource.enabled.is_(True)))).all())
        failed = False
        for source_id in ids:
            async with sessions() as db:
                source = await db.get(DataSource, source_id)
                run = await sync_source(db, source)
                await db.commit()
                print(f"{source.key}: {run.status}, fetched={run.fetched_count}, error={run.error_summary or '-'}")
                failed |= run.status != "succeeded"
        return 1 if failed else 0
    finally:
        await close_db()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18081)
    operations = parser.add_mutually_exclusive_group()
    operations.add_argument("--promote", metavar="EMAIL", help="Grant admin to an existing account in this local database, then exit")
    operations.add_argument("--sync-once", action="store_true", help="Sync enabled public sources once, then exit")
    args = parser.parse_args()
    backend = Path(__file__).resolve().parents[1]
    os.chdir(backend)
    configure(backend / ".public-local")
    command.upgrade(Config("alembic.ini"), "head")
    if args.promote:
        from scripts.admin import promote
        asyncio.run(promote(args.promote))
        return
    if args.sync_once:
        raise SystemExit(asyncio.run(sync_once()))
    print("Real public sources enabled; persistent local data in backend/.public-local")
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
