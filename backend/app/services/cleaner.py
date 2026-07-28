"""
InfoPulse — Data Cleaner
=========================
Preprocesses raw crawled text before feeding it to the LLM.
Reduces token usage by deduplication, truncation, and HTML stripping.
"""

import re
from typing import List

from app.services.crawler.base import RawPost


def clean_html(html: str) -> str:
    """Strip HTML tags, leaving only plain text."""
    clean = re.sub(r"<[^>]+>", "", html)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


def deduplicate(posts: List[RawPost]) -> List[RawPost]:
    """Remove near-duplicate posts by title similarity (prefix match)."""
    seen_titles: set[str] = set()
    unique: List[RawPost] = []
    for post in posts:
        # Use first 30 chars of title as dedup key
        key = post.title[:30].strip().lower()
        if key and key not in seen_titles:
            seen_titles.add(key)
            unique.append(post)
    return unique


def truncate_text(text: str, max_chars: int = 4000) -> str:
    """Truncate text at the nearest sentence boundary, keeping full context."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    # Cut back to the last sentence-ending punctuation
    last_period = max(
        truncated.rfind("。"),
        truncated.rfind(". "),
        truncated.rfind("！"),
        truncated.rfind("？"),
        truncated.rfind("\n"),
    )
    if last_period > max_chars * 0.5:
        return truncated[: last_period + 1]
    return truncated + "…"


def clean_posts(posts: List[RawPost]) -> str:
    """
    Convert a list of RawPost objects into a formatted text block
    suitable for the LLM prompt. Format:
        [平台] 标题：xxx
        内容：xxx
        ---
    """
    if not posts:
        return "（未获取到相关数据）"

    unique = deduplicate(posts)
    blocks = []
    for i, post in enumerate(unique[:30], 1):  # Max 30 posts to stay within token limits
        title = clean_html(post.title)[:120]
        content = clean_html(post.content)[:300]
        blocks.append(
            f"[{i}] {post.platform.upper()} | {post.author}\n"
            f"标题：{title}\n"
            f"内容：{content}\n"
        )

    text = "\n---\n".join(blocks)
    return truncate_text(text, max_chars=4000)
