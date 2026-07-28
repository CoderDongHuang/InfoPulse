"""Validate production integration credentials without printing their values."""
from __future__ import annotations
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import get_settings


def integration_errors(settings) -> list[str]:
    errors = list(settings.production_errors())
    required = {
        "LLM_API_KEY": settings.LLM_API_KEY,
        "SMTP_HOST": settings.SMTP_HOST,
        "SMTP_FROM": settings.SMTP_FROM,
        "SMTP_PASSWORD": settings.SMTP_PASSWORD,
        "S3_BUCKET": settings.S3_BUCKET,
        "S3_ACCESS_KEY": settings.S3_ACCESS_KEY,
        "S3_SECRET_KEY": settings.S3_SECRET_KEY,
        "GITHUB_TOKEN": settings.GITHUB_TOKEN,
    }
    for name, value in required.items():
        normalized = str(value or "").lower()
        if not value or "replace" in normalized or "your-" in normalized:
            errors.append(f"{name} is not configured")
    if settings.KNOWLEDGE_STORAGE_BACKEND != "s3":
        errors.append("KNOWLEDGE_STORAGE_BACKEND must be s3")
    for name, value in (("LLM_API_BASE", settings.LLM_API_BASE), ("S3_ENDPOINT_URL", settings.S3_ENDPOINT_URL)):
        if value and urlparse(value).scheme != "https":
            errors.append(f"{name} must use HTTPS")
    return errors


def main() -> int:
    errors = integration_errors(get_settings())
    if errors:
        for error in errors: print(f"BLOCKED: {error}")
        return 1
    print("Production deployment preflight passed without exposing credentials.")
    return 0


if __name__ == "__main__": raise SystemExit(main())
