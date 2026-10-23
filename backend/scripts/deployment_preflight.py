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
    for name, value in (("S3_BUCKET", settings.S3_BUCKET),):
        normalized = str(value or "").lower()
        if not value or "replace" in normalized or "your-" in normalized:
            errors.append(f"{name} is not configured")
    if settings.KNOWLEDGE_STORAGE_BACKEND != "s3":
        errors.append("KNOWLEDGE_STORAGE_BACKEND must be s3")

    if bool(settings.S3_ACCESS_KEY) != bool(settings.S3_SECRET_KEY):
        errors.append("S3_ACCESS_KEY and S3_SECRET_KEY must both be configured or both be empty")
    if bool(settings.SMTP_HOST) != bool(settings.SMTP_FROM):
        errors.append("SMTP_HOST and SMTP_FROM must both be configured or both be empty")
    if settings.SMTP_USERNAME and not settings.SMTP_PASSWORD:
        errors.append("SMTP_PASSWORD is required when SMTP_USERNAME is configured")
    if settings.SMTP_PASSWORD and not settings.SMTP_USERNAME:
        errors.append("SMTP_USERNAME is required when SMTP_PASSWORD is configured")

    for name, value in (
        ("LLM_API_BASE", settings.LLM_API_BASE),
        ("S3_ENDPOINT_URL", settings.S3_ENDPOINT_URL),
    ):
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
