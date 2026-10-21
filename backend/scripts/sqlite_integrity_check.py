"""Read-only historical SQLite foreign-key audit; never repairs or deletes data."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3


def check(path):
    path = Path(path).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        violations = [dict(zip(("table", "rowid", "parent", "foreign_key"), row))
                      for row in db.execute("PRAGMA foreign_key_check")]
    return {"ok": not violations, "violations": violations}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    result = check(parser.parse_args().database)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)
