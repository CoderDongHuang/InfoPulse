from collections import Counter
import re
from datetime import datetime, timedelta, timezone
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.intelligence import ChannelFollow, ContentItem, DataSource, Event, EventContent, Favorite, RecentView, RecommendationFeedback, SyncRun, WatchTopic

CHANNELS = {
 "ai": ("AI", ["ai", "artificial intelligence", "openai", "llm", "machine learning", "人工智能"]),
 "java": ("Java", ["java", "jvm", "spring"]),
 "robotics": ("机器人", ["robot", "robotics", "机器人"]),
 "open-source": ("开源", ["open source", "github", "开源"]),
 "funding": ("融资", ["funding", "investment", "融资", "investor"]),
 "products": ("产品", ["product", "launch", "release", "产品"]),
 "papers": ("论文", ["paper", "research", "arxiv", "论文"]),
}
RANGES = {"day": 1, "week": 7, "month": 30}

def dt(value): return value.isoformat() if value else None
def content_heat(item): return int(item.view_count or 0) + int(item.comment_count or 0) * 3 + int(item.like_count or 0) * 2 + int(item.share_count or 0) * 4
def keyword_matches(keyword, text):
    term = keyword.lower().strip()
    text = text.lower()
    if not term: return False
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text)) if term.isascii() else term in text
def content_dict(item, source, score=0, reasons=None):
    return {"id": item.id, "title": item.title, "summary": item.body[:240], "source": {"id": source.id, "key": source.key, "name": source.name}, "canonical_url": item.canonical_url, "published_at": dt(item.published_at), "heat": content_heat(item), "score": round(score, 2), "recommendation_reasons": reasons or []}

async def source_warnings(db):
    sources = (await db.scalars(select(DataSource).where(DataSource.enabled.is_(True)))).all()
    warnings = []
    for source in sources:
        if source.health_status != "healthy": warnings.append({"source_id": source.id, "source": source.name, "status": source.health_status, "message": source.last_error or "数据源尚未成功同步"})
    if not sources: warnings.append({"source_id": None, "source": "数据源中心", "status": "empty", "message": "尚未配置数据源，请先添加并同步真实来源"})
    return warnings

async def dashboard_data(db: AsyncSession, days=7):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    content_condition = [ContentItem.deleted_at.is_(None), ContentItem.published_at >= since]
    content_count = int(await db.scalar(select(func.count(ContentItem.id)).where(*content_condition)) or 0)
    event_count = int(await db.scalar(select(func.count(Event.id)).where(Event.deleted_at.is_(None), Event.last_activity_at >= since)) or 0)
    risk_count = int(await db.scalar(select(func.count(Event.id)).where(Event.deleted_at.is_(None), Event.last_activity_at >= since, Event.risk_score >= 40)) or 0)
    events = (await db.scalars(select(Event).where(Event.deleted_at.is_(None), Event.last_activity_at >= since).order_by(Event.heat_score.desc()).limit(20))).all()
    source_rows = (await db.execute(select(DataSource, func.count(ContentItem.id)).outerjoin(ContentItem).group_by(DataSource.id).order_by(func.count(ContentItem.id).desc()))).all()
    trend_rows = (await db.execute(select(func.date(ContentItem.published_at), func.count(ContentItem.id)).where(*content_condition).group_by(func.date(ContentItem.published_at)).order_by(func.date(ContentItem.published_at)))).all()
    def event_dict(e): return {"id": e.id, "title": e.title, "summary": e.summary, "heat_score": e.heat_score, "risk_score": e.risk_score, "confidence": e.confidence, "last_activity_at": dt(e.last_activity_at)}
    return {"has_data": content_count > 0, "metrics": {"content": content_count, "events": event_count, "risk_events": risk_count, "alerts": 0}, "hot_events": [event_dict(x) for x in events[:6]], "latest_events": [event_dict(x) for x in sorted(events, key=lambda x: x.last_activity_at or x.created_at, reverse=True)[:6]], "risk_events": [event_dict(x) for x in sorted((x for x in events if x.risk_score >= 40), key=lambda x: x.risk_score, reverse=True)[:6]], "trends": [{"date": str(day), "content": count} for day, count in trend_rows], "source_distribution": [{"source_id": s.id, "name": s.name, "count": count} for s, count in source_rows], "source_health": [{"id": s.id, "name": s.name, "status": s.health_status, "last_sync_at": dt(s.last_sync_at), "last_success_at": dt(s.last_success_at), "last_error": s.last_error} for s, _ in source_rows], "source_warnings": await source_warnings(db)}

async def discover_data(db: AsyncSession, user_id: str, channel="ai", range_name="day", page=1, page_size=20):
    since = datetime.now(timezone.utc) - timedelta(days=RANGES[range_name])
    rows = (await db.execute(select(ContentItem, DataSource).join(DataSource).where(ContentItem.deleted_at.is_(None), ContentItem.published_at >= since).order_by(ContentItem.published_at.desc()).limit(500))).all()
    topics = (await db.scalars(select(WatchTopic).where(WatchTopic.user_id == user_id, WatchTopic.enabled.is_(True)))).all()
    feedback = {x.target_id: x.feedback_type for x in (await db.scalars(select(RecommendationFeedback).where(RecommendationFeedback.user_id == user_id))).all()}
    keywords = CHANNELS[channel][1]
    ranked = []
    for item, source in rows:
        text = f"{item.title} {item.body} {' '.join(item.tags or [])}".lower()
        matched = [k for k in keywords if keyword_matches(k, text)]
        if not matched: continue
        if feedback.get(item.id) in {"not_interested", "irrelevant"}: continue
        age_hours = max(0, (datetime.now(timezone.utc) - (item.published_at if item.published_at.tzinfo else item.published_at.replace(tzinfo=timezone.utc))).total_seconds() / 3600)
        score = max(0, 30 - age_hours / 4) + min(40, content_heat(item) / 100) + len(matched) * 8
        reasons = [{"rule": "channel_match", "label": f"匹配 {CHANNELS[channel][0]} 频道", "evidence": matched[:3]}]
        topic_hits = [t.name for t in topics if any(keyword_matches(k, text) for k in ([t.name] + list(t.keywords or [])))]
        if topic_hits: score += 25; reasons.append({"rule": "watched_topic", "label": "命中你的关注主题", "evidence": topic_hits})
        if content_heat(item) > 0: reasons.append({"rule": "source_engagement", "label": "来源互动信号较强", "evidence": [str(content_heat(item))]})
        if feedback.get(item.id) in {"seen", "low_quality"}: score -= 20
        ranked.append((score, item, source, reasons))
    ranked.sort(key=lambda x: x[0], reverse=True); total = len(ranked); selected = ranked[(page-1)*page_size:page*page_size]
    return {"items": [content_dict(item, source, score, reasons) for score, item, source, reasons in selected], "page": page, "page_size": page_size, "total": total, "has_more": page*page_size < total, "has_data": bool(rows), "ranking_rule": "频道匹配 + 时效性 + 真实互动量 + 关注主题；反馈产生个人降权或隐藏", "source_warnings": await source_warnings(db)}

async def workspace_data(db: AsyncSession, user_id: str):
    topics = (await db.scalars(select(WatchTopic).where(WatchTopic.user_id == user_id, WatchTopic.enabled.is_(True)).order_by(WatchTopic.created_at.desc()))).all()
    attention = []
    for topic in topics:
        terms = [topic.name] + list(topic.keywords or []); count = 0
        for term in terms: count += int(await db.scalar(select(func.count(ContentItem.id)).where(ContentItem.deleted_at.is_(None), func.lower(ContentItem.title).contains(term.lower()))) or 0)
        attention.append({"id": topic.id, "name": topic.name, "count": count, "keywords": topic.keywords})
    recommendation = await discover_data(db, user_id, "ai", "day", 1, 5)
    favorites = [dict(target_type=x.target_type, target_id=x.target_id, created_at=dt(x.created_at)) for x in (await db.scalars(select(Favorite).where(Favorite.user_id == user_id).order_by(Favorite.created_at.desc()).limit(8))).all()]
    views = [dict(target_type=x.target_type, target_id=x.target_id, title=x.title, viewed_at=dt(x.viewed_at)) for x in (await db.scalars(select(RecentView).where(RecentView.user_id == user_id).order_by(RecentView.viewed_at.desc()).limit(8))).all()]
    return {"date": datetime.now(timezone.utc).date().isoformat(), "attention": attention, "recommendations": recommendation["items"], "favorites": favorites, "recent_reports": [], "recent_views": views, "tasks": [], "source_warnings": recommendation["source_warnings"]}
