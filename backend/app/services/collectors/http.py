"""Bounded HTTP retries shared by official API collectors."""

import asyncio
import ssl
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
import certifi


class UpstreamRateLimited(RuntimeError):
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"上游服务请求限流（HTTP 429），请在 {int(retry_after) + 1} 秒后重试")


def retry_after_seconds(value: str | None, default: float = 60) -> float:
    try:
        seconds = float(value)
        if not 0 <= seconds < float("inf"):
            return default
        return seconds
    except (TypeError, ValueError):
        try:
            date = parsedate_to_datetime(value)
            return max(0, (date - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return default


def public_ssl_context() -> ssl.SSLContext:
    """Verify against OS trust plus bundled public roots (including Windows).

    This supports an explicitly OS-trusted enterprise proxy without disabling
    hostname/certificate checks or silently accepting arbitrary certificates.
    """
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context


async def get_response(client: httpx.AsyncClient, url: str, *, attempts: int = 3, **kwargs) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = await client.get(url, **kwargs)
            # Do not turn one rate-limited request into three rapid requests.
            # Callers can defer work or use an independent official feed.
            if response.status_code == 429:
                raise UpstreamRateLimited(retry_after_seconds(response.headers.get("Retry-After")))
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            last_error = exc
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                break
            if attempt < attempts - 1:
                await asyncio.sleep(0.2 * (2**attempt))
    raise RuntimeError(f"Upstream request failed: {last_error}") from last_error

