"""Bounded HTTP retries shared by official API collectors."""

import asyncio
import ssl

import httpx
import certifi


def public_ssl_context() -> ssl.SSLContext:
    """Verify against OS trust plus bundled public roots (including Windows).

    This supports an explicitly OS-trusted enterprise proxy without disabling
    hostname/certificate checks or silently accepting arbitrary certificates.
    """
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context


async def get_response(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = await client.get(url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < 2:
                await asyncio.sleep(0.2 * (2**attempt))
    raise RuntimeError(f"Upstream request failed: {last_error}") from last_error

