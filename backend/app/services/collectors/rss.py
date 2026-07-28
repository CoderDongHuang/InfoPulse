"""Generic RSS 2.0 and Atom feed collector."""

import ipaddress
import socket
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx

from app.services.collectors.base import NormalizedContent
from app.services.collectors.http import get_response


class RssCollector:
    def __init__(self, feed_url: str, client: httpx.AsyncClient | None = None):
        self.feed_url = feed_url
        self._client = client

    async def collect(self, limit: int = 30) -> list[NormalizedContent]:
        validate_public_feed_url(self.feed_url, resolve_dns=self._client is None)
        if self._client:
            return await self._collect(self._client, limit)
        async with httpx.AsyncClient(timeout=12, follow_redirects=True, headers={"User-Agent": "InfoPulse/1.0"}) as client:
            return await self._collect(client, limit)

    async def _collect(self, client: httpx.AsyncClient, limit: int) -> list[NormalizedContent]:
        response = await get_response(client, self.feed_url)
        if len(response.content) > 5_000_000:
            raise ValueError("RSS feed exceeds 5 MB")
        root = ElementTree.fromstring(response.content)
        if root.tag.endswith("feed"):
            return self._atom(root, limit)
        return self._rss(root, limit)

    def _rss(self, root, limit):
        items = []
        for node in root.findall("./channel/item")[:limit]:
            title = _child_text(node, "title")
            link = _child_text(node, "link")
            guid = _child_text(node, "guid") or link
            if title and guid:
                items.append(NormalizedContent(
                    external_id=guid, canonical_url=link or self.feed_url, title=title,
                    body=_child_text(node, "description"), author_name=_child_text(node, "author"),
                    content_type="article", language="und", published_at=_rss_date(_child_text(node, "pubDate")),
                    is_original=None, raw_payload={"guid": guid, "link": link, "title": title},
                ))
        return items

    def _atom(self, root, limit):
        namespace = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""
        ns = {"a": namespace} if namespace else {}
        prefix = "a:" if namespace else ""
        items = []
        for node in root.findall(f"{prefix}entry", ns)[:limit]:
            title = _find_text(node, f"{prefix}title", ns)
            external_id = _find_text(node, f"{prefix}id", ns)
            link_node = node.find(f"{prefix}link", ns)
            link = link_node.attrib.get("href", "") if link_node is not None else ""
            if title and (external_id or link):
                author = node.find(f"{prefix}author", ns)
                items.append(NormalizedContent(
                    external_id=external_id or link, canonical_url=link or self.feed_url, title=title,
                    body=_find_text(node, f"{prefix}summary", ns) or _find_text(node, f"{prefix}content", ns),
                    author_name=_find_text(author, f"{prefix}name", ns) if author is not None else "",
                    content_type="article", language="und",
                    published_at=_iso_date(_find_text(node, f"{prefix}published", ns) or _find_text(node, f"{prefix}updated", ns)),
                    is_original=None, raw_payload={"id": external_id, "link": link, "title": title},
                ))
        return items


def validate_public_feed_url(url: str, resolve_dns: bool = True) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("RSS 地址必须是公开的 HTTP 或 HTTPS URL")
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".local"):
        raise ValueError("RSS 地址不能指向本地网络")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        addresses = []
        if resolve_dns:
            addresses = {ipaddress.ip_address(info[4][0]) for info in socket.getaddrinfo(host, None)}
    if any(address.is_private or address.is_loopback or address.is_link_local or address.is_reserved for address in addresses):
        raise ValueError("RSS 地址不能指向私有或保留网络")


def _child_text(node, name):
    child = node.find(name)
    return (child.text or "").strip() if child is not None else ""


def _find_text(node, path, namespaces):
    child = node.find(path, namespaces)
    return (child.text or "").strip() if child is not None else ""


def _rss_date(value):
    try:
        return parsedate_to_datetime(value) if value else None
    except (TypeError, ValueError):
        return None


def _iso_date(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
    except ValueError:
        return None

