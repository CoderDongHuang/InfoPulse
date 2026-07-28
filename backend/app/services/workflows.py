"""Business workflows shared by the public-opinion modules."""

import asyncio
import json
import logging
import re
import time
import urllib.parse
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.llm import complete_json, llm_is_configured
from app.services.cleaner import clean_posts
from app.services.crawler import get_crawler
from app.services.crawler.base import RawPost

logger = logging.getLogger(__name__)

POSITIVE_WORDS = ("支持", "喜欢", "优秀", "期待", "好评", "感动", "厉害", "值得")
NEGATIVE_WORDS = ("质疑", "失望", "反对", "翻车", "争议", "离谱", "愤怒", "投诉", "造假")
HOT_RANKING_CACHE_TTL_SECONDS = 300
_hot_ranking_cache: tuple[float, dict[str, Any]] | None = None
_hot_ranking_lock = asyncio.Lock()


async def collect_posts(
    keyword: str,
    platforms: list[str],
    max_items: int,
) -> tuple[list[RawPost], list[dict[str, Any]]]:
    """Collect sources concurrently; failures remain visible but non-fatal."""
    per_platform = max(3, min(30, max_items // max(len(platforms), 1)))

    async def collect(platform: str):
        crawler = get_crawler(platform)
        if crawler is None or not crawler.is_available():
            return [], {"platform": platform, "count": 0, "status": "unavailable"}
        try:
            posts = await asyncio.wait_for(
                crawler.search(keyword, per_platform),
                timeout=45 if platform == "tieba" else 22,
            )
            return posts, {
                "platform": platform,
                "count": len(posts),
                "status": "ok" if posts else "empty",
            }
        except Exception as exc:
            logger.warning("Crawler %s failed: %s", platform, exc)
            return [], {"platform": platform, "count": 0, "status": "failed"}
        finally:
            close = getattr(crawler, "close", None)
            if close:
                try:
                    await close()
                except Exception:
                    pass

    batches = await asyncio.gather(*(collect(item) for item in platforms))
    posts = [post for batch, _ in batches for post in batch]
    sources = [source for _, source in batches]
    deduped: dict[str, RawPost] = {}
    for post in posts:
        key = re.sub(r"\W+", "", f"{post.title}{post.content}")[:120]
        if key:
            deduped.setdefault(key, post)
    return list(deduped.values())[:max_items], sources


def _sentiment(text: str) -> str:
    positive = sum(word in text for word in POSITIVE_WORDS)
    negative = sum(word in text for word in NEGATIVE_WORDS)
    if positive > negative:
        return "positive"
    if negative > positive:
        return "negative"
    return "neutral"


def fallback_insight(keyword: str, posts: list[RawPost], sources: list[dict]) -> dict:
    sentiments = Counter(_sentiment(f"{p.title} {p.content}") for p in posts)
    total = max(len(posts), 1)
    platform_counts = Counter(p.platform for p in posts)
    representatives = [
        {
            "platform": post.platform,
            "content": (post.content or post.title)[:180],
            "stance": _sentiment(f"{post.title} {post.content}"),
            "url": post.url,
        }
        for post in posts[:6]
    ]
    key_points = []
    for platform, count in platform_counts.most_common(3):
        key_points.append({
            "label": f"{platform} 讨论焦点",
            "detail": f"共采集 {count} 条公开讨论，主要围绕事件进展、当事人回应和网友判断展开。",
            "stance": "neutral",
        })
    return {
        "topic": keyword,
        "overview": f"围绕“{keyword}”共整理 {len(posts)} 条公开讨论。当前信息仍在变化，建议结合来源链接持续核验。",
        "sentiment": {
            "positive": round(sentiments["positive"] * 100 / total),
            "neutral": round(sentiments["neutral"] * 100 / total),
            "negative": round(sentiments["negative"] * 100 / total),
        },
        "confidence": min(92, 45 + len(posts) * 2),
        "volume": len(posts),
        "sources": sources,
        "key_points": key_points or [{"label": "样本不足", "detail": "暂未形成稳定观点聚类。", "stance": "neutral"}],
        "representative_opinions": representatives,
        "risks": ["社交平台内容存在二次转述，请优先核验原始来源。"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def analyze_insight(keyword: str, posts: list[RawPost], sources: list[dict]) -> dict:
    fallback = fallback_insight(keyword, posts, sources)
    if not llm_is_configured() or not posts:
        return fallback
    prompt = clean_posts(posts)[:18000]
    system = """你是中文互联网舆情分析师。只基于给定公开样本分析，不补造事实。
输出严格 JSON，字段必须包含：overview；sentiment(positive,neutral,negative，合计100)；confidence(0-100)；
key_points(3-6项，每项label/detail/stance)；representative_opinions(4-8项，每项platform/content/stance/url)；risks(字符串数组)。"""
    try:
        result = await complete_json(system, f"话题：{keyword}\n公开样本：\n{prompt}", max_tokens=2600)
        return {**fallback, **result, "topic": keyword, "volume": len(posts), "sources": sources}
    except Exception as exc:
        logger.warning("Insight LLM fallback: %s", exc)
        return fallback


async def generate_mouthpiece(payload: dict) -> dict:
    tones = {"sharp": "犀利直接", "humorous": "幽默有梗", "gentle": "温柔克制", "rational": "理性清晰"}
    source = payload["source_text"]
    fallback = {
        "title": source[:24].rstrip("，。！？") or "把话说清楚",
        "body": source.strip(),
        "hashtags": ["#表达", "#今日想法", "#InfoPulse"],
        "alternatives": [source.strip(), f"说到底，{source.strip()}", f"我更愿意这样表达：{source.strip()}"],
        "tone": payload["tone"],
        "intensity": payload["intensity"],
    }
    if not llm_is_configured():
        return fallback
    system = """你是中文社交媒体文案编辑。保留用户事实与立场，不攻击具体个人，不编造经历。
输出严格 JSON：title、body、hashtags(3-6个)、alternatives(3个)。文案自然、可直接发布。"""
    request = (
        f"场景：{payload['scene']}\n风格：{tones[payload['tone']]}\n"
        f"情绪强度：{payload['intensity']}/100\n篇幅：{payload['length']}\n原话：{source}"
    )
    try:
        result = await complete_json(system, request, temperature=0.75, max_tokens=1800)
        return {**fallback, **result}
    except Exception as exc:
        logger.warning("Mouthpiece LLM fallback: %s", exc)
        return fallback


async def build_timeline(topic: str, posts: list[RawPost], sources: list[dict]) -> dict:
    fallback_nodes = [
        {
            "time": post.publish_time or "时间待核验",
            "title": post.title[:60] or "公开讨论出现",
            "detail": post.content[:220] or post.title[:220],
            "source": post.platform,
            "url": post.url,
            "confidence": 60 if post.publish_time else 42,
        }
        for post in posts[:10]
    ]
    fallback = {
        "topic": topic,
        "summary": f"已从 {len(posts)} 条公开样本中整理事件线索，时间与事实仍需以原始信源为准。",
        "nodes": fallback_nodes,
        "unknowns": ["部分社交平台发布时间或转述来源无法独立验证。"],
        "sources": sources,
    }
    if not llm_is_configured() or not posts:
        return fallback
    system = """你是事实核查编辑。将样本整理为时间线，合并重复信息，不把网友猜测写成事实。
输出严格 JSON：summary、nodes、unknowns。nodes 每项含 time/title/detail/source/url/confidence。"""
    try:
        result = await complete_json(system, f"事件：{topic}\n样本：\n{clean_posts(posts)[:18000]}", max_tokens=2600)
        return {**fallback, **result, "topic": topic, "sources": sources}
    except Exception as exc:
        logger.warning("Timeline LLM fallback: %s", exc)
        return fallback


async def fetch_hot_rankings() -> list[dict]:
    """Return Weibo's current hot-search list for dashboard consumers."""
    return (await fetch_hot_ranking_payload())["items"]


async def fetch_hot_ranking_payload() -> dict[str, Any]:
    """Fetch Weibo's public hot band and expose its real availability state."""
    global _hot_ranking_cache
    now = time.monotonic()
    if _hot_ranking_cache and now - _hot_ranking_cache[0] < HOT_RANKING_CACHE_TTL_SECONDS:
        return _hot_ranking_cache[1]

    async with _hot_ranking_lock:
        now = time.monotonic()
        if _hot_ranking_cache and now - _hot_ranking_cache[0] < HOT_RANKING_CACHE_TTL_SECONDS:
            return _hot_ranking_cache[1]

        payload = await _request_hot_rankings()
        _hot_ranking_cache = (time.monotonic(), payload)
        return payload


async def _request_hot_rankings() -> dict[str, Any]:
    items: list[dict] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://weibo.com/hot/search",
    }
    try:
        async with httpx.AsyncClient(timeout=8, headers=headers, follow_redirects=True) as client:
            response = await client.get("https://weibo.com/ajax/statuses/hot_band")
            response.raise_for_status()
            band = response.json().get("data", {}).get("band_list", [])
            for entry in band:
                title = str(entry.get("note") or entry.get("word") or "").strip()
                if not title or entry.get("is_ad"):
                    continue
                items.append({
                    "rank": len(items) + 1,
                    "platform": "微博",
                    "title": title,
                    "heat": int(entry.get("num") or 0),
                    "url": f"https://s.weibo.com/weibo?q={urllib.parse.quote('#' + title + '#')}",
                    "category": entry.get("category") or "热搜",
                    "label": entry.get("label_name") or entry.get("icon_desc") or "",
                })
                if len(items) >= 30:
                    break
    except Exception as exc:
        logger.warning("Weibo hot ranking unavailable: %s", exc)

    return {
        "items": items,
        "source": "微博热搜榜",
        "source_url": "https://s.weibo.com/top/summary",
        "status": "live" if items else "unavailable",
        "message": "数据来自微博公开热搜榜" if items else "微博热搜暂时无法访问，请稍后刷新",
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


async def explain_hot_item(item: dict) -> str:
    if not llm_is_configured():
        return f"“{item['title']}”热度上升，主要来自集中讨论与平台推荐，建议结合原始内容查看完整背景。"
    try:
        result = await complete_json(
            "你是热搜编辑。输出严格 JSON，仅含 explanation，80字以内，不编造事实。",
            json.dumps(item, ensure_ascii=False),
            max_tokens=220,
        )
        return result.get("explanation", "")
    except Exception:
        return f"“{item['title']}”正在形成集中讨论，点击来源可查看上下文。"
