"""Freeze and verify the public OpenAPI operation contract."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app

SNAPSHOT = Path(__file__).resolve().parents[2] / "docs" / "api-contract-v1.json"
METHODS = {"get", "post", "put", "patch", "delete"}


def contract() -> dict[str, dict[str, dict]]:
    result = {}
    for path, item in sorted(app.openapi()["paths"].items()):
        operations = {}
        for method, operation in sorted(item.items()):
            if method not in METHODS:
                continue
            operations[method] = {
                "operationId": operation.get("operationId"),
                "deprecated": bool(operation.get("deprecated", False)),
                "responses": sorted(operation.get("responses", {}).keys()),
            }
        result[path] = operations
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    current = {"version": 1, "policy": "docs/api-deprecation-policy.md", "paths": contract()}
    if args.update:
        SNAPSHOT.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Updated {SNAPSHOT}")
        return 0
    if not SNAPSHOT.exists() or json.loads(SNAPSHOT.read_text(encoding="utf-8")) != current:
        print("BLOCKED: OpenAPI contract changed. Review compatibility, then run with --update.")
        return 1
    print(f"API contract verified: {len(current['paths'])} paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
