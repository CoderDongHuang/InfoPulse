"""Inventory formal source/docs, validate syntax, and index documentation claims."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
SCOPES = ["backend/app", "backend/tests", "backend/scripts", "backend/alembic", "frontend/src", "frontend/tests", "frontend/scripts", "sdk", "deploy", ".github", "docs"]
EXCLUDED = {"node_modules", "__pycache__", "dist", ".git", ".venv", ".venv-audit", "images", "probes"}
EXTENSIONS = {".py", ".ts", ".mjs", ".js", ".vue", ".css", ".html", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".ini", ".conf", ".svg", ".mako"}
paths = set(p for p in ROOT.iterdir() if p.is_file() and (p.suffix in EXTENSIONS or p.name.startswith("Dockerfile")))
for scope in SCOPES:
    paths.update(p for p in (ROOT / scope).rglob("*") if p.is_file() and not EXCLUDED.intersection(p.relative_to(ROOT / scope).parts) and (p.suffix in EXTENSIONS or p.name.startswith("Dockerfile")))
paths.update(p for p in (ROOT / "backend").iterdir() if p.is_file() and (p.suffix in {".py", ".txt", ".ini", ".toml"} or p.name.startswith("Dockerfile")))
paths.update(p for p in (ROOT / "frontend").iterdir() if p.is_file() and (p.suffix in EXTENSIONS or p.name.startswith("Dockerfile")))
paths.update(ROOT / path for path in ("LICENSE", ".gitignore", "backend/.dockerignore", "backend/.env.example", "frontend/.dockerignore", "frontend/.gitignore") if (ROOT / path).is_file())
rows, errors, docs = [], [], []
for path in sorted(paths):
    raw = path.read_bytes(); value = raw.decode("utf-8-sig")
    relative = path.relative_to(ROOT).as_posix()
    row = {"path": relative, "lines": len(value.splitlines()), "sha256": hashlib.sha256(raw).hexdigest()}
    rows.append(row)
    try:
        if path.suffix == ".py": ast.parse(value, filename=relative)
        # TypeScript configuration accepts JSONC; vue-tsc/build validates these.
        if path.suffix == ".json" and not path.name.startswith("tsconfig"): json.loads(value)
    except Exception as exc: errors.append({"path": relative, "error": str(exc)})
    if path.suffix == ".md":
        lines = value.splitlines()
        headings = [line for line in lines if line.startswith("#")]
        pending = [f"{i}: {line}" for i, line in enumerate(lines, 1) if re.search(r"\[ \]|TODO|待完成|尚未|不支持|未完成|阶段.*完成|已完成|生产级|形式化|后量子|TEE|BFT", line)]
        docs.append({"path": relative, "lines": row["lines"], "headings": headings, "claims_and_gaps": pending})
counts = Counter("/".join(row["path"].split("/")[:2]) for row in rows)
out = {"scope": "Formal source/configuration/documentation; excludes dependencies, runtime data, uploads, images and audit probes. All files inventoried and syntax/claim-scanned; this is not a claim of manual line-by-line review.", "files": rows, "syntax_errors": errors, "counts": dict(counts), "documentation": docs}
Path(__file__).with_suffix(".results.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"files": len(rows), "lines": sum(row["lines"] for row in rows), "markdown_files": len(docs), "syntax_errors": errors}, ensure_ascii=False, indent=2))
