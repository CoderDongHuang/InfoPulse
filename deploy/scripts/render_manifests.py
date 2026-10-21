"""Render immutable image tags and public hosts into Kubernetes manifests."""
from __future__ import annotations
import argparse
from pathlib import Path
import re


PHASES = ("all", "bootstrap", "preflight", "migrate", "canary", "promote")


def select_phase(text, phase):
    selected = []
    for document in re.split(r"(?m)^---\s*$", text):
        kind = re.search(r"(?m)^kind:\s*(\S+)", document).group(1)
        name = re.search(r"(?:name:\s*)([a-zA-Z0-9_.-]+)", document).group(1)
        if kind in {"Namespace", "ConfigMap"}: stage = "bootstrap"
        elif kind == "Job": stage = "preflight" if name.startswith("preflight-") else "migrate"
        elif name == "api-canary" or kind == "NetworkPolicy": stage = "canary"
        else: stage = "promote"
        if phase == "all" or stage == phase: selected.append(document.strip())
    return "\n---\n".join(selected) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--canary-version", required=True)
    parser.add_argument("--api-host", required=True)
    parser.add_argument("--app-host", required=True)
    parser.add_argument("--phase", choices=PHASES, default="all")
    parser.add_argument("--repository", default="coderdonghuang/infopulse")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9_.-]+/[a-z0-9_.-]+", args.repository):
        raise SystemExit("repository is invalid")
    for value in (args.version, args.canary_version):
        if len(value)>40 or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*",value):
            raise SystemExit("image version must be a lowercase DNS-compatible tag up to 40 characters")
    for host in (args.api_host,args.app_host):
        if not re.fullmatch(r"[a-z0-9.-]+",host) or "." not in host:
            raise SystemExit("public host is invalid")
    text = Path(args.source).read_text(encoding="utf-8")
    text = text.replace("CANARY_VERSION", args.canary_version).replace("VERSION", args.version)
    text = text.replace("ghcr.io/coderdonghuang/infopulse", f"ghcr.io/{args.repository}")
    # Version config references so bootstrap never mutates a running release.
    text = text.replace("infopulse-config", f"infopulse-config-{args.version}")
    text = text.replace("api.example.com", args.api_host).replace("app.example.com", args.app_host)
    if "VERSION" in text or "api.example.com" in text or "app.example.com" in text:
        raise SystemExit("manifest still contains placeholders")
    Path(args.output).write_text(select_phase(text, args.phase), encoding="utf-8")


if __name__ == "__main__":
    main()
