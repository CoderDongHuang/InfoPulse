"""Isolated harness around the actual dedicated worker; never reads personal .env."""
import argparse
import asyncio
import os
import re
from pathlib import Path
from sqlalchemy.engine import make_url


def configure(database_url, storage_path):
    url = make_url(database_url)
    if (url.drivername != "postgresql+asyncpg" or url.host not in {"127.0.0.1", "localhost"}
            or url.username != "audit" or not re.fullmatch(r"infopulse_recovery_audit_[a-f0-9]{16}", url.database or "")):
        raise ValueError("Only a uniquely named local recovery audit database is allowed")
    from app.config import Settings, get_settings
    Settings.model_config["env_file"] = None
    for key in Settings.model_fields:
        os.environ.pop(key, None)
    os.environ.update({"DATABASE_URL": database_url, "AUTO_CREATE_TABLES": "false",
                       "KNOWLEDGE_STORAGE_PATH": str(Path(storage_path).resolve()),
                       "KNOWLEDGE_WORKER_POLL_SECONDS": "1", "CRAWLER_ENABLED": "false",
                       "TASK_SCHEDULER_ENABLED": "false", "MEDIA_WORKER_ENABLED": "false",
                       "RUN_BACKGROUND_WORKERS_IN_API": "false"})
    get_settings.cache_clear()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--storage-path", required=True, type=Path)
    parser.add_argument("--pause-marker", type=Path)
    parser.add_argument("--ready-marker", type=Path)
    args = parser.parse_args()
    configure(args.database_url, args.storage_path)
    # Pause only the interrupted worker after the production claim commits.
    if args.pause_marker:
        from app.services import knowledge
        async def pause(*_args, **_kwargs):
            args.pause_marker.write_text("claimed", encoding="utf-8")
            await asyncio.Event().wait()
        knowledge.process_document = pause
    from app import worker
    if args.ready_marker:
        original_init = worker.init_db
        async def initialized():
            await original_init()
            args.ready_marker.write_text("connected", encoding="utf-8")
        worker.init_db = initialized
    asyncio.run(worker.run("knowledge"))


if __name__ == "__main__":
    main()
