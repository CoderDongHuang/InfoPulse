"""
InfoPulse — Bilibili Crawler
==============================
B站搜索+评论 API 非常开放，无需登录即可获取大量数据。
"""

import asyncio
import random
from typing import List

import httpx

from app.config import get_settings
from app.services.crawler.base import BaseCrawler, RawPost, RawComment

settings = get_settings()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

BILI_SEARCH = "https://api.bilibili.com/x/web-interface/search/type"
BILI_REPLY = "https://api.bilibili.com/x/v2/reply"


class BilibiliCrawler(BaseCrawler):
    platform_name = "bilibili"

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "application/json",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Referer": "https://www.bilibili.com/",
                    "Origin": "https://www.bilibili.com",
                },
            )
        return self._client

    def is_available(self) -> bool:
        return True  # B站 API 无需登录

    async def search(self, keyword: str, max_items: int = 50) -> List[RawPost]:
        client = await self._get_client()
        posts: List[RawPost] = []
        page = 1

        while len(posts) < max_items:
            try:
                resp = await client.get(BILI_SEARCH, params={
                    "search_type": "video",
                    "keyword": keyword,
                    "page": page,
                    "page_size": min(20, max_items - len(posts)),
                })
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"[Bilibili] Search error: {e}")
                break

            if data.get("code") != 0:
                break

            items = data.get("data", {}).get("result", [])
            if not items:
                break

            for item in items:
                aid = item.get("aid") or item.get("id")
                posts.append(RawPost(
                    post_id=f"av{aid}",
                    title=(item.get("title", "") or "").replace('<em class="keyword">', "").replace("</em>", "")[:120],
                    content=(item.get("description", "") or "")[:500],
                    author=item.get("author", ""),
                    publish_time=str(item.get("pubdate", "")),
                    url=f"https://www.bilibili.com/video/av{aid}",
                    platform="bilibili",
                ))

            page += 1
            await self._sleep_random()

        return posts[:max_items]

    async def get_comments(self, post_id: str, max_items: int = 50) -> List[RawComment]:
        """Fetch video comments. post_id format: 'av12345'."""
        client = await self._get_client()
        comments: List[RawComment] = []

        # Extract AV number from post_id
        oid = post_id.replace("av", "")

        page = 1
        while len(comments) < max_items:
            try:
                resp = await client.get(BILI_REPLY, params={
                    "type": 1,  # 1 = video comment
                    "oid": oid,
                    "pn": page,
                    "ps": min(20, max_items - len(comments)),
                    "sort": 2,  # 2 = hottest
                })
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                break

            if data.get("code") != 0:
                break

            replies = data.get("data", {}).get("replies", [])
            if not replies:
                break

            for r in replies:
                comments.append(RawComment(
                    comment_id=str(r.get("rpid", "")),
                    post_id=post_id,
                    content=r.get("content", {}).get("message", "")[:500],
                    author=r.get("member", {}).get("uname", "匿名"),
                    like_count=r.get("like", 0),
                    publish_time=str(r.get("ctime", "")),
                ))

            page += 1

            # Stop after 3 pages
            if page > 3:
                break

        return comments[:max_items]

    @staticmethod
    async def _sleep_random():
        await asyncio.sleep(random.uniform(0.8, 2.0))

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
