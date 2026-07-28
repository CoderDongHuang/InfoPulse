"""Render immutable image tags and public hosts into Kubernetes manifests."""
from __future__ import annotations
import argparse
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--canary-version", required=True)
    parser.add_argument("--api-host", required=True)
    parser.add_argument("--app-host", required=True)
    args = parser.parse_args()
    for value in (args.version, args.canary_version):
        if len(value)>40 or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*",value):
            raise SystemExit("image version must be a lowercase DNS-compatible tag up to 40 characters")
    for host in (args.api_host,args.app_host):
        if not re.fullmatch(r"[a-z0-9.-]+",host) or "." not in host:
            raise SystemExit("public host is invalid")
    text = Path(args.source).read_text(encoding="utf-8")
    text = text.replace("CANARY_VERSION", args.canary_version).replace("VERSION", args.version)
    text = text.replace("api.example.com", args.api_host).replace("app.example.com", args.app_host)
    if "VERSION" in text or "example.com" in text:
        raise SystemExit("manifest still contains placeholders")
    Path(args.output).write_text(text, encoding="utf-8")
