"""Create a localhost SQLite configuration with unique secrets; never overwrite .env."""
import argparse
import secrets
from pathlib import Path


def initialize(target: Path) -> None:
    template = Path(__file__).resolve().parents[1] / ".env.example"
    replacements = {
        "DATABASE_URL": "sqlite+aiosqlite:///./infopulse.db",
        "JWT_SECRET_KEY": secrets.token_urlsafe(48),
        "PLATFORM_ENCRYPTION_KEY": secrets.token_urlsafe(48),
        "METRICS_TOKEN": secrets.token_urlsafe(32),
        "LLM_API_KEY": "",
        "CRAWLER_ENABLED": "false",
        "MEDIA_WORKER_ENABLED": "false",
    }
    lines = []
    for line in template.read_text(encoding="utf-8").splitlines():
        name = line.partition("=")[0]
        lines.append(f"{name}={replacements[name]}" if name in replacements else line)
    with target.open("x", encoding="utf-8", newline="\n") as output:
        output.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / ".env")
    args = parser.parse_args()
    try:
        initialize(args.output)
    except FileExistsError:
        parser.exit(1, "Configuration exists; refusing to overwrite it.\n")
    print("Local configuration created. Run alembic upgrade head, then start the API on 127.0.0.1.")
