"""GitHub repository discovery through the official REST Search API."""

from datetime import datetime, timedelta, timezone

import httpx

from app.services.collectors.base import NormalizedContent
from app.services.collectors.http import get_response


class GitHubCollector:
    base_url = "https://api.github.com"

    def __init__(self, client: httpx.AsyncClient | None = None, token: str = ""):
        self._client = client
        self._token = token

    async def collect(self, limit: int = 30) -> list[NormalizedContent]:
        if self._client:
            return await self._collect(self._client, limit)
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        async with httpx.AsyncClient(timeout=12, headers=headers, follow_redirects=True) as client:
            return await self._collect(client, limit)

    async def _collect(self, client: httpx.AsyncClient, limit: int) -> list[NormalizedContent]:
        since = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
        response = await get_response(client, f"{self.base_url}/search/repositories", params={
            "q": f"created:>={since}", "sort": "stars", "order": "desc", "per_page": min(limit, 100),
        })
        payload = response.json()
        return [self._normalize(item) for item in payload.get("items", [])[:limit] if item.get("id")]

    @staticmethod
    def _normalize(item: dict) -> NormalizedContent:
        owner = item.get("owner") or {}
        return NormalizedContent(
            external_id=str(item["id"]), canonical_url=str(item["html_url"]),
            title=str(item.get("full_name") or item.get("name") or ""), body=str(item.get("description") or ""),
            author_name=str(owner.get("login") or ""), author_external_id=str(owner.get("id") or ""),
            content_type="repository", language="en", region="global",
            published_at=_parse_datetime(item.get("created_at")),
            comment_count=int(item.get("open_issues_count") or 0), like_count=int(item.get("stargazers_count") or 0),
            share_count=int(item.get("forks_count") or 0), is_original=True, raw_payload=item,
        )


def _parse_datetime(value: str | None):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None

