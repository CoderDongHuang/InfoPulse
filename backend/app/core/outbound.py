"""Bounded public HTTP requests, with DNS resolution pinned per redirect hop."""
import asyncio
import ipaddress
import socket
from urllib.parse import urljoin

import httpx


def public_addresses(url: str, *, https_only: bool = False, resolve_dns: bool = True) -> list[str]:
    parsed = httpx.URL(url)
    if parsed.scheme not in ({"https"} if https_only else {"http", "https"}) or not parsed.host or parsed.userinfo or parsed.fragment:
        raise ValueError("Outbound URL must be a public HTTP(S) URL without credentials or fragment")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in (80, 443):
        raise ValueError("Only standard HTTP(S) ports are allowed")
    host = parsed.host.lower().rstrip(".")
    if host == "localhost" or host.endswith((".local", ".localhost")):
        raise ValueError("Local network targets are forbidden")
    try:
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        if not resolve_dns:
            return []
        try:
            addresses = sorted({row[4][0] for row in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
        except OSError as exc:
            raise ValueError("Outbound hostname cannot be resolved") from exc
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError("Outbound target must resolve only to public addresses")
    return addresses


async def public_request(method: str, url: str, *, client: httpx.AsyncClient | None = None,
                         https_only: bool = False, max_bytes: int = 5_000_000,
                         max_redirects: int = 4, timeout: float = 12, **kwargs) -> httpx.Response:
    return await asyncio.wait_for(_public_request(method, url, client=client, https_only=https_only,
        max_bytes=max_bytes, max_redirects=max_redirects, timeout=timeout, **kwargs), timeout=timeout)


async def _public_request(method, url, *, client, https_only, max_bytes, max_redirects, timeout, **kwargs):
    # Injected clients are a test seam, not an API option. Production always pins DNS
    # and ignores proxy environment variables; TLS still verifies the original host.
    mock = client is not None and isinstance(client._transport, httpx.MockTransport)
    current = url
    request_headers = kwargs.pop("headers", {})
    for hop in range(max_redirects + 1):
        addresses = await asyncio.to_thread(public_addresses, current, https_only=https_only, resolve_dns=not mock)
        original = httpx.URL(current)
        target = original if mock else original.copy_with(host=addresses[0])
        headers = {**request_headers, "Host": original.netloc.decode("ascii")}
        owned = client is None
        transport = client or httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False)
        try:
            async with transport.stream(method, target, headers=headers, follow_redirects=False,
                                        extensions={"sni_hostname": original.host}, **kwargs) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    if method != "GET" or hop == max_redirects or not response.headers.get("location"):
                        raise ValueError("Outbound redirect is not allowed")
                    current = urljoin(current, response.headers["location"])
                    continue
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(data) + len(chunk) > max_bytes:
                        raise ValueError("Outbound response exceeds size limit")
                    data.extend(chunk)
                return httpx.Response(response.status_code, headers=response.headers, content=bytes(data), request=httpx.Request(method, current))
        finally:
            if owned:
                await transport.aclose()
    raise ValueError("Outbound redirect limit exceeded")
