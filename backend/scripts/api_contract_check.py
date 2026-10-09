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


def structural(value):
    """Exclude prose, retain the validation and authentication contract."""
    if isinstance(value, dict):
        return {key: structural(item) for key, item in sorted(value.items()) if key not in {"description", "summary", "title", "example", "examples", "externalDocs"}}
    if isinstance(value, list):
        return [structural(item) for item in value]
    return value


def contract(schema=None) -> dict:
    schema = schema or app.openapi()
    result = {}
    for path, item in sorted(schema["paths"].items()):
        operations = {}
        for method, operation in sorted(item.items()):
            if method not in METHODS:
                continue
            operations[method] = {
                "operationId": operation.get("operationId"),
                "deprecated": bool(operation.get("deprecated", False)),
                "parameters": structural(operation.get("parameters", [])),
                "requestBody": structural(operation.get("requestBody")),
                "responses": structural(operation.get("responses", {})),
                "security": structural(operation.get("security", schema.get("security", []))),
            }
        result[path] = operations
    return {"paths": result, "components": structural(schema.get("components", {}))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    current = {"version": 2, "policy": "docs/api-deprecation-policy.md", **contract()}
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
