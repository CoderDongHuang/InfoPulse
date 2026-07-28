"""DEV Community collector using its public Articles API."""

from datetime import datetime

import httpx

from app.services.collectors.base import NormalizedContent
from app.services.collectors.http import get_response


class DevToCollector:
    base_url = "https://dev.to/api"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def collect(self, limit: int = 30) -> list[NormalizedContent]:
        if self._client:
            return await self._collect(self._client, limit)
        async with httpx.AsyncClient(timeout=12, headers={"Accept": "application/json"}) as client:
            return await self._collect(client, limit)

    async def _collect(self, client: httpx.AsyncClient, limit: int) -> list[NormalizedContent]:
        response = await get_response(client, f"{self.base_url}/articles", params={"top": 1, "per_page": min(limit, 100)})
        return [self._normalize(item) for item in response.json()[:limit] if item.get("id")]

    @staticmethod
    def _normalize(item: dict) -> NormalizedContent:
        user = item.get("user") or {}
        return NormalizedContent(
            external_id=str(item["id"]), canonical_url=str(item.get("canonical_url") or item.get("url") or ""),
            title=str(item.get("title") or ""), body=str(item.get("description") or ""),
            author_name=str(user.get("name") or item.get("user", {}).get("username") or ""),
            author_external_id=str(user.get("user_id") or user.get("username") or ""),
            content_type="article", language="en", region="global",
            published_at=_parse_datetime(item.get("published_at")),
            comment_count=int(item.get("comments_count") or 0), like_count=int(item.get("positive_reactions_count") or 0),
            is_original=True, raw_payload=item,
        )


def _parse_datetime(value: str | None):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None

