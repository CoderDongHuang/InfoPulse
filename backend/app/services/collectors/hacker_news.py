"""Hacker News collector backed by the official Firebase API."""

import asyncio
from datetime import datetime, timezone

import httpx

from app.services.collectors.base import NormalizedContent


class HackerNewsCollector:
    base_url = "https://hacker-news.firebaseio.com/v0"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def collect(self, limit: int = 30) -> list[NormalizedContent]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")

        if self._client is not None:
            return await self._collect(self._client, limit)

        timeout = httpx.Timeout(12.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            return await self._collect(client, limit)

    async def _collect(self, client: httpx.AsyncClient, limit: int) -> list[NormalizedContent]:
        story_ids = await self._get_json(client, f"{self.base_url}/topstories.json")
        if not isinstance(story_ids, list):
            raise ValueError("Hacker News top stories response is not a list")

        payloads = await asyncio.gather(
            *(self._get_json(client, f"{self.base_url}/item/{story_id}.json") for story_id in story_ids[:limit])
        )
        items: list[NormalizedContent] = []
        for payload in payloads:
            if not isinstance(payload, dict) or payload.get("type") != "story" or payload.get("deleted"):
                continue
            story_id = str(payload["id"])
            title = str(payload.get("title") or "").strip()
            if not title:
                continue
            discussion_url = f"https://news.ycombinator.com/item?id={story_id}"
            items.append(
                NormalizedContent(
                    external_id=story_id,
                    canonical_url=str(payload.get("url") or discussion_url),
                    title=title,
                    body=str(payload.get("text") or ""),
                    author_name=str(payload.get("by") or ""),
                    author_external_id=str(payload.get("by") or ""),
                    content_type="article",
                    language="en",
                    region="global",
                    published_at=datetime.fromtimestamp(int(payload["time"]), tz=timezone.utc)
                    if payload.get("time")
                    else None,
                    comment_count=int(payload.get("descendants") or 0),
                    like_count=int(payload.get("score") or 0),
                    is_original=True,
                    raw_payload=payload,
                )
            )
        return items

    @staticmethod
    async def _get_json(client: httpx.AsyncClient, url: str):
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.2 * (2**attempt))
        raise RuntimeError(f"Hacker News request failed: {last_error}") from last_error

