"""Exercise the migration round trip on a disposable SQLite database only."""
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
from scripts.test_suites import configure

with tempfile.TemporaryDirectory(prefix="infopulse-migration-audit-") as temporary:
    configure(Path(temporary))
    from app.config import get_settings
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    get_settings().DATABASE_URL = "sqlite+aiosqlite:///" + (Path(temporary) / "audit.db").as_posix()
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    heads = ScriptDirectory.from_config(config).get_heads()
    assert len(heads) == 1, heads
    command.upgrade(config, "head")
    command.downgrade(config, "20260729_0013")
    command.upgrade(config, "head")
    result = {"database": "disposable SQLite", "heads": heads,
              "steps": ["empty -> head", "head -> 20260729_0013", "20260729_0013 -> head"],
              "passed": True, "production_postgresql_tested": False}
    Path(__file__).with_suffix(".results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
