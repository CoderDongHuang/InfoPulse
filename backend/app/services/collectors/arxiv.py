"""arXiv collector using the official Atom export API."""

import asyncio
import logging
import re
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import monotonic
from weakref import WeakKeyDictionary
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup

from app.services.collectors.base import NormalizedContent
from app.services.collectors.http import UpstreamRateLimited, get_response, public_ssl_context

ATOM = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
DC = "{http://purl.org/dc/elements/1.1/}"


@dataclass
class _RequestState:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    next_request_at: float = 0
    cooldowns: dict[str, float] = field(default_factory=dict)
    cache: dict[int, tuple[float, list[NormalizedContent]]] = field(default_factory=dict)


# Share limits across connection tests, manual syncs and the scheduler in a
# process. Separate loops (and injected test clients) must not share async locks.
_states: WeakKeyDictionary = WeakKeyDictionary()


class ArxivCollector:
    base_url = "https://export.arxiv.org/api"
    feed_url = "https://rss.arxiv.org/rss/cs.AI+cs.LG+cs.CL"
    request_interval = 3.0
    cache_seconds = 300.0

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def collect(self, limit: int = 30) -> list[NormalizedContent]:
        limit = min(max(limit, 1), 100)
        key = self._client if self._client is not None else asyncio.get_running_loop()
        state = _states.setdefault(key, _RequestState())
        async with state.lock:
            cached = state.cache.get(limit)
            if cached and cached[0] > monotonic():
                return deepcopy(cached[1])
            if self._client:
                items = await self._collect(self._client, limit, state)
            else:
                async with httpx.AsyncClient(timeout=10, verify=public_ssl_context(), headers={"User-Agent": "InfoPulse/1.0 (+https://github.com/CoderDongHuang/InfoPulse)"}) as client:
                    items = await self._collect(client, limit, state)
            state.cache[limit] = (monotonic() + self.cache_seconds, deepcopy(items))
            return items

    async def _request(self, client, state, url, **kwargs):
        remaining = state.cooldowns.get(url, 0) - monotonic()
        if remaining > 0:
            raise UpstreamRateLimited(remaining)
        await asyncio.sleep(max(0, state.next_request_at - monotonic()))
        # Reserve spacing before I/O so cancellation also respects the interval.
        state.next_request_at = monotonic() + self.request_interval
        try:
            return await get_response(client, url, attempts=1, **kwargs)
        except UpstreamRateLimited as exc:
            state.cooldowns[url] = monotonic() + max(self.request_interval, exc.retry_after)
            raise

    async def _collect(self, client: httpx.AsyncClient, limit: int, state: _RequestState) -> list[NormalizedContent]:
        try:
            response = await self._request(client, state, f"{self.base_url}/query", params={
                "search_query": "cat:cs.AI OR cat:cs.LG OR cat:cs.CL", "sortBy": "submittedDate",
                "sortOrder": "descending", "max_results": limit,
            })
            root = ElementTree.fromstring(response.content)
            if root.tag != f"{{{ATOM['atom']}}}feed":
                raise ValueError("arXiv API 未返回有效 Atom 数据")
            entries = root.findall("atom:entry", ATOM)
            if any("arxiv.org/api/errors" in _text(entry, "atom:id") for entry in entries):
                raise ValueError("arXiv API 返回查询错误")
            return [self._normalize(entry) for entry in entries[:limit]]
        except (RuntimeError, httpx.HTTPError, ElementTree.ParseError, ValueError) as api_error:
            logging.getLogger(__name__).info("arXiv API unavailable; trying official RSS: %s", api_error)
            try:
                response = await self._request(client, state, self.feed_url)
                return self._parse_rss(response.content, limit)
            except (RuntimeError, httpx.HTTPError, ElementTree.ParseError, ValueError) as feed_error:
                raise RuntimeError(f"arXiv 暂时无法更新。API：{api_error}；官方 RSS：{feed_error}。已有论文仍保留，稍后自动重试。") from feed_error

    @staticmethod
    def _parse_rss(content: bytes, limit: int) -> list[NormalizedContent]:
        root = ElementTree.fromstring(content)
        channel = root.find("channel")
        if root.tag != "rss" or channel is None:
            raise ValueError("arXiv 官方 RSS 未返回有效订阅数据")
        items = {}
        for node in channel.findall("item"):
            url = (node.findtext("link") or "").strip()
            title = " ".join((node.findtext("title") or "").split())
            if not url.startswith(("https://arxiv.org/abs/", "http://arxiv.org/abs/")) or not title:
                continue
            external_id = url.split("/abs/", 1)[1]
            # Official feeds often use an unversioned link and a versioned OAI
            # guid. Match the API's versioned id to avoid duplicate ingestion.
            guid = (node.findtext("guid") or "").removeprefix("oai:arXiv.org:")
            if re.fullmatch(re.escape(re.sub(r"v\d+$", "", external_id)) + r"v\d+", guid):
                external_id = guid
            date = node.findtext("pubDate") or channel.findtext("pubDate")
            author = (node.findtext(f"{DC}creator") or "").strip()
            categories = [x.text.strip() for x in node.findall("category") if x.text]
            item = NormalizedContent(
                external_id=external_id, canonical_url=url.replace("http://", "https://", 1), title=title,
                body=BeautifulSoup(node.findtext("description") or "", "html.parser").get_text(" ", strip=True),
                author_name=author, author_external_id=author.split(",")[0].strip(),
                content_type="paper", language="en", region="global", is_original=True,
                published_at=parsedate_to_datetime(date) if date else None,
                raw_payload={"id": url, "authors": [author] if author else [], "categories": categories, "feed_url": ArxivCollector.feed_url},
            )
            items.setdefault(external_id, item)
        if channel.findall("item") and not items:
            raise ValueError("arXiv 官方 RSS 未包含可识别的论文")
        # An empty daily feed is valid; an HTML/error payload is not.
        return sorted(items.values(), key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[:limit]

    @staticmethod
    def _normalize(entry: ElementTree.Element) -> NormalizedContent:
        url = _text(entry, "atom:id")
        external_id = url.rsplit("/", 1)[-1]
        authors = [(_text(author, "atom:name")) for author in entry.findall("atom:author", ATOM)]
        return NormalizedContent(
            external_id=external_id, canonical_url=url, title=" ".join(_text(entry, "atom:title").split()),
            body=" ".join(_text(entry, "atom:summary").split()), author_name=", ".join(authors),
            author_external_id=authors[0] if authors else "", content_type="paper", language="en", region="global",
            published_at=_parse_datetime(_text(entry, "atom:published")), is_original=True,
            raw_payload={"id": url, "authors": authors, "categories": [node.attrib.get("term") for node in entry.findall("atom:category", ATOM)]},
        )


def _text(node: ElementTree.Element, path: str) -> str:
    child = node.find(path, ATOM)
    return (child.text or "").strip() if child is not None else ""


def _parse_datetime(value: str | None):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None

