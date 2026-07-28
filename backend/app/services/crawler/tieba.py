"""
InfoPulse — Baidu Tieba Crawler
=================================
Uses Playwright for the SPA-rendered search page.
Tieba switched to client-side rendering, so httpx alone can't get results.
"""

import asyncio
import random
import re
import time
from typing import List
from urllib.parse import urlencode

from app.config import get_settings
from app.services.crawler.base import BaseCrawler, RawPost, RawComment
from app.services.crawler.browser_manager import BrowserManager
from app.services.crawler.stealth_patcher import apply_stealth

settings = get_settings()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]


class TiebaCrawler(BaseCrawler):
    platform_name = "tieba"

    def __init__(self):
        self._manager = BrowserManager()

    def is_available(self) -> bool:
        try:
            from playwright.async_api import async_playwright  # noqa: F401
            return True
        except ImportError:
            return False

    async def search(self, keyword: str, max_items: int = 50) -> List[RawPost]:
        if not self.is_available():
            print("[Tieba] Playwright not installed")
            return []

        posts: List[RawPost] = []

        page = None
        try:
            page = await self._manager.get_page()
            await apply_stealth(page)

            # Set cookies to bypass Baidu verification
            if settings.TIEBA_COOKIE:
                cookies = []
                for pair in settings.TIEBA_COOKIE.split(";"):
                    pair = pair.strip()
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        cookies.append({
                            "name": k, "value": v,
                            "domain": ".baidu.com", "path": "/",
                        })
                await page.context.add_cookies(cookies)

            search_url = f"https://tieba.baidu.com/f/search/res?{urlencode({'ie': 'utf-8', 'qw': keyword})}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # Extract post links — try title attr first, then text content
            links = await page.evaluate("""
                () => {
                    const results = [];
                    const seen = new Set();
                    document.querySelectorAll(\"a[href*='/p/']\").forEach(a => {
                        const href = a.getAttribute('href');
                        const tid = href.split('/p/')[1]?.split('?')[0];
                        if (!href || !tid || seen.has(tid)) return;
                        seen.add(tid);
                        // Try multiple sources for the title
                        let text = a.getAttribute('title') || '';
                        if (!text || text.length < 2) {
                            text = (a.innerText || a.textContent || '').trim();
                        }
                        if (!text || text.length < 2) {
                            const p = a.closest('div, li, span');
                            if (p) text = (p.innerText || '').trim().split('\\n')[0] || '';
                        }
                        results.push({href, text: text.slice(0,120) || '\\uff08\\u65e0\\u6807\\u9898\\uff09'});
                    });
                    return results;
                }
            """)
            for link in links:
                tid = link["href"].split("/p/")[1].split("?")[0]
                title = link["text"][:120]
                if len(title) > 1:
                    posts.append(RawPost(
                        post_id=tid,
                        title=title,
                        content=title[:500],
                        author="",
                        publish_time="",
                        url=f"https://tieba.baidu.com{link['href']}",
                        platform="tieba",
                    ))
                if len(posts) >= max_items:
                    break

        except Exception as e:
            print(f"[Tieba] Search failed: {e}")
        finally:
            try:
                if page is not None:
                    await page.close()
            finally:
                await self._manager.mark_task_done()

        return posts[:max_items]

    async def get_comments(self, post_id: str, max_items: int = 50) -> List[RawComment]:
        if not self.is_available():
            return []

        comments: List[RawComment] = []
        page = None
        try:
            page = await self._manager.get_page()
            await page.goto(f"https://tieba.baidu.com/p/{post_id}", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            for _ in range(3):
                contents = await page.evaluate("""
                    () => {
                        const results = [];
                        document.querySelectorAll('.d_post_content').forEach(el => {
                            const text = el.innerText.trim();
                            if (text) results.push(text);
                        });
                        return results;
                    }
                """)
                for content in contents:
                    if len(content) > 2:
                        comments.append(RawComment(
                            comment_id=str(len(comments)),
                            post_id=post_id,
                            content=content[:500],
                            author="",
                            like_count=0,
                        ))
                if len(comments) >= 5:
                    break
                await asyncio.sleep(1)

        except Exception as e:
            print(f"[Tieba] Comments failed: {e}")
        finally:
            try:
                if page is not None:
                    await page.close()
            finally:
                await self._manager.mark_task_done()

        return comments[:max_items]

    async def close(self):
        pass  # BrowserManager is a singleton
