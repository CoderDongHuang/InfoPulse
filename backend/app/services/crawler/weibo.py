"""
InfoPulse — Weibo Crawler
===========================
Uses Weibo's mobile API (m.weibo.cn) which is more accessible
than the desktop version. No login required for basic search.
"""

import asyncio
import random
import urllib.parse
from typing import List

import httpx

from app.config import get_settings
from app.services.crawler.base import BaseCrawler, RawPost, RawComment

settings = get_settings()

USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

WEIBO_SEARCH_URL = "https://m.weibo.cn/api/container/getIndex"


class WeiboCrawler(BaseCrawler):
    """Crawl Weibo search results via the mobile API."""

    platform_name = "weibo"

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Referer": "https://m.weibo.cn/",
                    "X-Requested-With": "XMLHttpRequest",
                    "Cookie": settings.WEIBO_COOKIE or "",
                },
            )
        return self._client

    def is_available(self) -> bool:
        return True

    async def search(self, keyword: str, max_items: int = 50) -> List[RawPost]:
        client = await self._get_client()
        posts: List[RawPost] = []
        page = 1

        # Warn if no cookie configured
        if not settings.WEIBO_COOKIE:
            print("[Weibo] No cookie configured — search may fail (HTTP 432). "
                  "Set WEIBO_COOKIE in .env to enable Weibo crawling.")

        # Weibo containerid for keyword search
        containerid = f"100103type=1&q={urllib.parse.quote(keyword)}"

        while len(posts) < max_items:
            params = {
                "containerid": containerid,
                "page": page,
            }

            try:
                resp = await client.get(WEIBO_SEARCH_URL, params=params)
                resp.raise_for_status()
                try:
                    data = resp.json()
                except Exception:
                    # Weibo may return HTML when rate-limited
                    print(f"[Weibo] Non-JSON response (likely rate-limited), status={resp.status_code}")
                    break
            except Exception as e:
                print(f"[Weibo] Search request failed: {e}")
                break

            if data.get("ok") != 1:
                break

            cards = data.get("data", {}).get("cards", [])
            if not cards:
                break

            for card in cards:
                if card.get("card_type") != 9:  # type 9 = text post
                    continue
                mblog = card.get("mblog", {})
                if not mblog:
                    continue

                # Clean up HTML from text
                text = mblog.get("text", "")
                text = _strip_html(text)

                posts.append(RawPost(
                    post_id=str(mblog.get("id", "")),
                    title=text[:80].replace("\n", " "),
                    content=text[:500],
                    author=mblog.get("user", {}).get("screen_name", "未知用户"),
                    publish_time=str(mblog.get("created_at", "")),
                    url=f"https://m.weibo.cn/detail/{mblog.get('id')}",
                    platform="weibo",
                ))

                if len(posts) >= max_items:
                    break

            page += 1
            delay = random.uniform(
                settings.CRAWLER_REQUEST_INTERVAL_MIN,
                settings.CRAWLER_REQUEST_INTERVAL_MAX,
            )
            await asyncio.sleep(delay)

        return posts[:max_items]

    async def get_comments(self, post_id: str, max_items: int = 50) -> List[RawComment]:
        """Fetch hot comments for a Weibo post."""
        client = await self._get_client()
        comments: List[RawComment] = []
        comment_url = "https://m.weibo.cn/comments/hotflow"
        page = 1

        while len(comments) < max_items:
            params = {"id": post_id, "mid": post_id, "max_id_type": "0"}
            if page > 1:
                params["max_id"] = str(page)

            try:
                resp = await client.get(comment_url, params=params)
                resp.raise_for_status()
                try:
                    data = resp.json()
                except Exception:
                    break
            except Exception:
                break

            if data.get("ok") != 1:
                break

            for item in data.get("data", {}).get("data", []):
                comments.append(RawComment(
                    comment_id=str(item.get("id", "")),
                    post_id=post_id,
                    content=_strip_html(item.get("text", "")),
                    author=item.get("user", {}).get("screen_name", "未知"),
                    like_count=item.get("like_count", 0),
                    publish_time=str(item.get("created_at", "")),
                ))
                if len(comments) >= max_items:
                    break

            if len(comments) >= max_items:
                break
            page += 1
            await asyncio.sleep(random.uniform(1, 2))

        return comments[:max_items]

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


def _strip_html(text: str) -> str:
    """Remove HTML tags and entities from Weibo text."""
    import re
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"\s+", " ", text)
    return text.strip()
