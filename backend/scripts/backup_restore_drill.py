"""Create a PostgreSQL archive and restore it into an explicitly named drill database."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
import tempfile


def run(command, env):
    subprocess.run(command, env=env, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", required=True, help="libpq PostgreSQL URL")
    parser.add_argument("--restore-url", required=True, help="empty drill database URL")
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    if args.confirm != "RESTORE_INTO_EMPTY_DRILL_DATABASE":
        raise SystemExit("explicit drill confirmation is required")
    if args.source_url == args.restore_url or "postgres" not in args.restore_url:
        raise SystemExit("source and restore databases must be distinct PostgreSQL targets")
    env = os.environ.copy()
    with tempfile.TemporaryDirectory(prefix="infopulse-backup-drill-") as directory:
        archive = Path(directory) / "backup.dump"
        run(["pg_dump", "--format=custom", "--no-owner", "--file", str(archive), args.source_url], env)
        run(["pg_restore", "--exit-on-error", "--no-owner", "--dbname", args.restore_url, str(archive)], env)
        run(["psql", args.restore_url, "--command", "SELECT count(*) AS migration_count FROM alembic_version;"], env)
    print("Backup and restore drill completed successfully.")


if __name__ == "__main__":
    main()
