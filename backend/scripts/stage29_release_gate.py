"""Local release-candidate gate for the converged Stage 20-29 product."""
from __future__ import annotations

import os
import subprocess
import sys

ENV = {
    **os.environ,
    "DATABASE_URL": "sqlite+aiosqlite:///./stage29-release-gate.db",
    "LLM_API_KEY": "",
    "GITHUB_TOKEN": "",
    "TASK_SCHEDULER_ENABLED": "false",
    "ORCHESTRATION_WORKER_ENABLED": "false",
}
COMMANDS = [
    [sys.executable, "-m", "compileall", "-q", "app", "tests", "scripts"],
    [sys.executable, "scripts/api_contract_check.py"],
    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
    [sys.executable, "-m", "alembic", "upgrade", "head"],
]


def main() -> int:
    for command in COMMANDS:
        print("+", " ".join(command), flush=True)
        result = subprocess.run(command, env=ENV, check=False)
        if result.returncode:
            return result.returncode
    print("Stage 29 release-candidate gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
