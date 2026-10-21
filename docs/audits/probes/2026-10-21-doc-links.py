"""Check local Markdown link targets in the audit's complete document inventory.

This checks file existence, not remote URLs or heading anchors. Fenced examples
are excluded. Findings are candidates for manual review, not automatic defects.
"""
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[3]
inventory = json.loads(Path(__file__).with_name("2026-10-21-inventory.results.json").read_text(encoding="utf-8"))
checked, missing = 0, []
for document in inventory["documentation"]:
    path = ROOT / document["path"]
    fenced = False
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if re.match(r"\s*(```|~~~)", line):
            fenced = not fenced
            continue
        if fenced:
            continue
        for match in re.finditer(r"!?\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)", line):
            target = match.group(1).strip("<>")
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            checked += 1
            destination = (path.parent / unquote(url.path)).resolve()
            if not destination.exists():
                missing.append({"document": document["path"], "line": line_number, "target": target})
result = {"markdown_files": len(inventory["documentation"]), "local_links_checked": checked,
          "missing_targets": missing, "anchors_and_remote_urls_checked": False}
Path(__file__).with_suffix(".results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
