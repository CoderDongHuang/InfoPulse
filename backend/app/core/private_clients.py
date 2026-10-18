"""Bounded public-only transports for account-supplied service destinations."""
import asyncio
import smtplib
import socket
import ssl
from contextlib import asynccontextmanager, contextmanager

import httpx

from app.core.outbound import public_addresses


class BoundedStream(httpx.AsyncByteStream):
    def __init__(self, stream, limit=8_000_000):
        self.stream, self.limit = stream, limit

    async def __aiter__(self):
        size = 0
        async for chunk in self.stream:
            size += len(chunk)
            if size > self.limit:
                raise ValueError("Model response exceeds size limit")
            yield chunk

    async def aclose(self):
        await self.stream.aclose()


class PublicModelTransport(httpx.AsyncBaseTransport):
    """Pin every request, preserve TLS SNI, and keep SSE genuinely streaming."""
    def __init__(self):
        self.transport = httpx.AsyncHTTPTransport(retries=0)

    async def handle_async_request(self, request):
        addresses = await asyncio.to_thread(public_addresses, str(request.url), https_only=True)
        original = request.url
        request.headers["Host"] = original.netloc.decode("ascii")
        request.extensions["sni_hostname"] = original.host
        request.url = original.copy_with(host=addresses[0])
        try:
            response = await self.transport.handle_async_request(request)
        finally:
            request.url = original
        response.stream = BoundedStream(response.stream)
        return response

    async def aclose(self):
        await self.transport.aclose()


def model_http_client(timeout):
    return httpx.AsyncClient(transport=PublicModelTransport(), follow_redirects=False,
                             trust_env=False, timeout=timeout)


@asynccontextmanager
async def managed_model_client(factory):
    client = factory()
    try:
        yield client
    except asyncio.TimeoutError:
        raise asyncio.TimeoutError("Model request timed out") from None
    except Exception:
        raise RuntimeError("Model request failed; check endpoint, model, credential and provider quota") from None
    finally:
        close = getattr(client, "close", None)
        if close:
            await close()


@contextmanager
def smtp_connection(settings):
    """SMTP always uses TLS, public DNS pinning and the original TLS hostname."""
    host, port = settings.SMTP_HOST, settings.SMTP_PORT
    if port not in (465, 587):
        raise ValueError("Only SMTP TLS ports 465 and 587 are supported")
    addresses = public_addresses("https://" + host, https_only=True)
    context = ssl.create_default_context()

    class PinnedSMTP(smtplib.SMTP):
        def _get_socket(self, host, port, timeout):
            return socket.create_connection((addresses[0], port), timeout)

    class PinnedSMTPSSL(smtplib.SMTP_SSL):
        def _get_socket(self, host, port, timeout):
            raw = socket.create_connection((addresses[0], port), timeout)
            try:
                return context.wrap_socket(raw, server_hostname=host)
            except BaseException:
                raw.close()
                raise

    smtp_class = PinnedSMTPSSL if port == 465 else PinnedSMTP
    with smtp_class(host, port, timeout=10) as smtp:
        if port == 587:
            smtp.starttls(context=context)
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        yield smtp
