"""Fail the release when production configuration or migration topology is unsafe."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings


def main() -> int:
    settings = get_settings()
    errors = settings.production_errors()
    heads = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"], cwd=ROOT, capture_output=True, text=True
    )
    if heads.returncode != 0:
        errors.append("alembic heads failed")
    elif len([line for line in heads.stdout.splitlines() if line.strip()]) != 1:
        errors.append("database migrations must have exactly one head")
    if errors:
        for error in errors:
            print(f"BLOCKED: {error}")
        return 1
    print("Production configuration and migration topology are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
