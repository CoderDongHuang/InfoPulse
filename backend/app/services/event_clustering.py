"""Deterministic first-pass event clustering and explainable scoring."""

import hashlib
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence import ContentItem, DataSource, Event, EventContent, EventEntity

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.+-]{1,}|[\u4e00-\u9fff]{2,}")
STOPWORDS = {"the", "and", "for", "with", "from", "this", "that", "发布", "最新", "一个", "进行", "相关"}
RISK_WORDS = {"breach", "vulnerability", "attack", "outage", "scam", "ban", "lawsuit", "泄露", "漏洞", "攻击", "故障", "诈骗", "封禁", "诉讼", "风险"}


def tokens(text: str) -> set[str]:
    return {item.lower() for item in TOKEN_RE.findall(text or "") if item.lower() not in STOPWORDS}


def normalized_entities(content: ContentItem) -> set[str]:
    values = set()
    for entity in content.entities or []:
        value = entity.get("name") if isinstance(entity, dict) else entity
        if value: values.add(str(value).strip())
    for item in TOKEN_RE.findall(content.title or ""):
        if (item[:1].isupper() and len(item) > 2) or re.fullmatch(r"[\u4e00-\u9fff]{2,8}", item):
            values.add(item)
    return {value for value in values if value}


def similarity(left: ContentItem, right: ContentItem) -> float:
    left_tokens = tokens(f"{left.title} {left.body[:500]}")
    right_tokens = tokens(f"{right.title} {right.body[:500]}")
    union = left_tokens | right_tokens
    lexical = len(left_tokens & right_tokens) / len(union) if union else 0
    left_entities, right_entities = normalized_entities(left), normalized_entities(right)
    entity_union = left_entities | right_entities
    entity_score = len(left_entities & right_entities) / len(entity_union) if entity_union else 0
    return round(lexical * 0.72 + entity_score * 0.28, 4)


def event_scores(contents: list[ContentItem], source_count: int, now: datetime | None = None) -> tuple[float, float, float]:
    now = now or datetime.now(timezone.utc)
    engagement = sum(int(item.like_count or 0) + int(item.comment_count or 0) * 2 + int(item.share_count or 0) * 3 for item in contents)
    latest = max((item.published_at for item in contents if item.published_at), default=now)
    if latest.tzinfo is None: latest = latest.replace(tzinfo=timezone.utc)
    freshness = max(0.0, 1 - (now - latest).total_seconds() / (7 * 86400))
    heat = min(100.0, math.log1p(engagement) * 9 + len(contents) * 4 + source_count * 7 + freshness * 18)
    combined = " ".join(f"{item.title} {item.body}" for item in contents).lower()
    risk_hits = sum(combined.count(word) for word in RISK_WORDS)
    negative = sum(item.sentiment == "negative" for item in contents)
    risk = min(100.0, risk_hits * 14 + negative * 9)
    entity_coverage = len(set().union(*(normalized_entities(item) for item in contents)))
    confidence = min(98.0, 30 + len(contents) * 8 + source_count * 13 + min(entity_coverage, 5) * 3)
    return round(heat, 2), round(risk, 2), round(confidence, 2)


async def cluster_recent_content(db: AsyncSession, hours: int = 168, threshold: float = 0.24) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    linked = select(EventContent.content_item_id)
    rows = (await db.execute(
        select(ContentItem, DataSource).join(DataSource).where(
            ContentItem.deleted_at.is_(None), ContentItem.published_at >= cutoff,
            ContentItem.id.not_in(linked),
        ).order_by(ContentItem.published_at, ContentItem.id)
    )).all()
    contents = [row[0] for row in rows]
    source_by_content = {row[0].id: row[1] for row in rows}
    parent = list(range(len(contents)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]; index = parent[index]
        return index

    def union(left, right):
        left_root, right_root = find(left), find(right)
        if left_root != right_root: parent[right_root] = left_root

    for left in range(len(contents)):
        for right in range(left + 1, len(contents)):
            left_at, right_at = contents[left].published_at, contents[right].published_at
            if left_at and right_at:
                if left_at.tzinfo is None: left_at = left_at.replace(tzinfo=timezone.utc)
                if right_at.tzinfo is None: right_at = right_at.replace(tzinfo=timezone.utc)
                if abs((left_at - right_at).total_seconds()) > 72 * 3600: continue
            score = similarity(contents[left], contents[right])
            shared_entity = bool(normalized_entities(contents[left]) & normalized_entities(contents[right]))
            if score >= threshold or (shared_entity and score >= 0.12): union(left, right)

    groups: dict[int, list[ContentItem]] = {}
    for index, content in enumerate(contents): groups.setdefault(find(index), []).append(content)
    created_events = []
    for group in groups.values():
        if not group: continue
        group.sort(key=lambda item: (int(item.like_count or 0) + int(item.comment_count or 0), item.published_at or cutoff), reverse=True)
        primary = group[0]
        sources = {source_by_content[item.id].id for item in group}
        heat, risk, confidence = event_scores(group, len(sources))
        fingerprint = hashlib.sha1("|".join(sorted(item.id for item in group)).encode()).hexdigest()[:12]
        event = Event(
            title=primary.title[:500], slug=f"event-{fingerprint}", summary=(primary.body or primary.title)[:600],
            category=_category(group), status="rising" if heat >= 60 else "detected", heat_score=heat,
            risk_score=risk, confidence=confidence,
            started_at=min((item.published_at for item in group if item.published_at), default=None),
            last_activity_at=max((item.published_at for item in group if item.published_at), default=None),
            manual_locked=False,
        )
        db.add(event); await db.flush()
        for index, content in enumerate(group):
            db.add(EventContent(event_id=event.id, content_item_id=content.id,
                relevance_score=1.0 if index == 0 else similarity(primary, content), is_primary=index == 0, added_by="system"))
        entity_counts = Counter(entity for content in group for entity in normalized_entities(content))
        for name, count in entity_counts.most_common(10):
            db.add(EventEntity(event_id=event.id, name=name[:300], entity_type="keyword", mention_count=count))
        created_events.append(event)
    await db.flush()
    return {"scanned_count": len(contents), "created_count": len(created_events), "event_ids": [item.id for item in created_events]}


def _category(contents: list[ContentItem]) -> str:
    kinds = Counter(item.content_type for item in contents)
    primary = kinds.most_common(1)[0][0]
    return {"repository": "open-source", "paper": "research", "article": "technology"}.get(primary, primary)

