"""arXiv collector using the official Atom export API."""

from datetime import datetime
from xml.etree import ElementTree

import httpx

from app.services.collectors.base import NormalizedContent
from app.services.collectors.http import get_response

ATOM = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivCollector:
    base_url = "https://export.arxiv.org/api"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def collect(self, limit: int = 30) -> list[NormalizedContent]:
        if self._client:
            return await self._collect(self._client, limit)
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": "InfoPulse/1.0 contact@infopulse.local"}) as client:
            return await self._collect(client, limit)

    async def _collect(self, client: httpx.AsyncClient, limit: int) -> list[NormalizedContent]:
        response = await get_response(client, f"{self.base_url}/query", params={
            "search_query": "cat:cs.AI OR cat:cs.LG OR cat:cs.CL", "sortBy": "submittedDate",
            "sortOrder": "descending", "max_results": min(limit, 100),
        })
        root = ElementTree.fromstring(response.content)
        return [self._normalize(entry) for entry in root.findall("atom:entry", ATOM)[:limit]]

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

