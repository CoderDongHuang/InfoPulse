"""Start an isolated localhost acceptance API without reading the user's .env."""
import argparse
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import uvicorn

from app.config import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default="sqlite+aiosqlite:///./audit-product.db")
    parser.add_argument("--redis-url", default="redis://127.0.0.1:16379/0")
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args()
    os.chdir(Path(__file__).resolve().parents[1])
    # This entry point must never use private provider credentials or storage.
    Settings.model_config["env_file"] = None
    for key in Settings.model_fields:
        os.environ.pop(key, None)
    os.environ.update({
        "DATABASE_URL": args.database_url,
        "REDIS_URL": args.redis_url,
        "JWT_SECRET_KEY": "acceptance-test-only-secret-not-for-real-use-0000",
        "PLATFORM_ENCRYPTION_KEY": "acceptance-test-only-encryption-not-for-real-use-0000",
        "METRICS_TOKEN": "acceptance-test-only-metrics-000000",
        "KNOWLEDGE_STORAGE_PATH": "./data/audit-knowledge",
        "TASK_SCHEDULER_ENABLED": "false",
        "CRAWLER_ENABLED": "false",
        "MEDIA_WORKER_ENABLED": "false",
    })
    command.upgrade(Config("alembic.ini"), "head")
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
