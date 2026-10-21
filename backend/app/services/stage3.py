from collections import Counter
import re
from datetime import datetime, timedelta, timezone
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.intelligence import ChannelFollow, ContentItem, DataSource, Event, EventContent, Favorite, RecentView, RecommendationFeedback, SyncRun, WatchTopic
from app.models.intelligence import Report
from app.services.personalization import saved_targets, history_title
from app.models.analysis_history import AnalysisHistory

CHANNELS = {
 "all": ("全部", []),
 "ai": ("AI", ["ai", "artificial intelligence", "openai", "llm", "machine learning", "人工智能"]),
 "java": ("Java", ["java", "jvm", "spring"]),
 "robotics": ("机器人", ["robot", "robotics", "机器人"]),
 "open-source": ("开源", ["open source", "github", "开源"]),
 "funding": ("融资", ["funding", "investment", "融资", "investor"]),
 "products": ("产品", ["product", "launch", "release", "产品"]),
 "papers": ("论文", ["paper", "research", "arxiv", "论文"]),
}
RANGES = {"day": 1, "week": 7, "month": 30}

def dt(value): return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat() if value else None
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
    content_condition = [ContentItem.deleted_at.is_(None), func.coalesce(ContentItem.published_at, ContentItem.fetched_at) >= since]
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
    observed_at = func.coalesce(ContentItem.published_at, ContentItem.fetched_at)
    rows = (await db.execute(select(ContentItem, DataSource).join(DataSource).where(ContentItem.deleted_at.is_(None), observed_at >= since).order_by(observed_at.desc(), ContentItem.id).limit(500))).all()
    topics = (await db.scalars(select(WatchTopic).where(WatchTopic.user_id == user_id, WatchTopic.enabled.is_(True)))).all()
    feedback = {x.target_id: x.feedback_type for x in (await db.scalars(select(RecommendationFeedback).where(RecommendationFeedback.user_id == user_id))).all()}
    keywords = CHANNELS[channel][1]
    ranked = []
    for item, source in rows:
        text = f"{item.title} {item.body} {' '.join(item.tags or [])}".lower()
        matched = [k for k in keywords if keyword_matches(k, text)]
        type_match = (channel == "papers" and item.content_type == "paper") or (channel == "open-source" and item.content_type == "repository")
        if channel != "all" and not matched and not type_match: continue
        if feedback.get(item.id) in {"not_interested", "irrelevant"}: continue
        timestamp = item.published_at or item.fetched_at
        age_hours = max(0, (datetime.now(timezone.utc) - (timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc))).total_seconds() / 3600)
        score = max(0, 30 - age_hours / 4) + min(40, content_heat(item) / 100) + len(matched) * 8
        reasons = [{"rule": "public_source" if channel == "all" else "channel_match", "label": "来自公开数据源" if channel == "all" else f"匹配 {CHANNELS[channel][0]} 频道", "evidence": matched[:3] or [item.content_type if type_match else source.name]}]
        topic_hits = [t.name for t in topics if any(keyword_matches(k, text) for k in ([t.name] + list(t.keywords or [])))]
        if topic_hits: score += 25; reasons.append({"rule": "watched_topic", "label": "命中你的关注主题", "evidence": topic_hits})
        if content_heat(item) > 0: reasons.append({"rule": "source_engagement", "label": "来源互动信号较强", "evidence": [str(content_heat(item))]})
        if feedback.get(item.id) in {"seen", "low_quality"}: score -= 20
        ranked.append((score, item, source, reasons))
    ranked.sort(key=lambda x: x[0], reverse=True); total = len(ranked); selected = ranked[(page-1)*page_size:page*page_size]
    return {"items": [content_dict(item, source, score, reasons) for score, item, source, reasons in selected], "page": page, "page_size": page_size, "total": total, "has_more": page*page_size < total, "has_data": bool(rows), "ranking_rule": "频道匹配 + 时效性 + 真实互动量 + 关注主题；反馈产生个人降权或隐藏", "source_warnings": await source_warnings(db)}

async def workspace_data(db: AsyncSession, user_id: str):
    topics = (await db.scalars(select(WatchTopic).where(WatchTopic.user_id == user_id, WatchTopic.enabled.is_(True)).order_by(WatchTopic.created_at.desc()))).all()
    followed = (await db.scalars(select(ChannelFollow).where(ChannelFollow.user_id == user_id).order_by(ChannelFollow.created_at.desc()))).all()
    observed_at = func.coalesce(ContentItem.published_at, ContentItem.fetched_at)
    candidates = (await db.execute(select(ContentItem, DataSource).join(DataSource).where(
        ContentItem.deleted_at.is_(None)).order_by(observed_at.desc(), ContentItem.id).limit(500))).all() if topics or followed else []
    def matches(item, terms):
        text = f"{item.title} {item.body} {' '.join(item.tags or [])}"
        return any(keyword_matches(term, text) for term in terms)
    attention = []
    for topic in topics:
        count = sum(matches(item, [topic.name] + list(topic.keywords or [])) for item, _ in candidates)
        attention.append({"id": topic.id, "name": topic.name, "count": count, "keywords": topic.keywords})
    followed_channels = [{"id": row.channel_id, "name": CHANNELS[row.channel_id][0]} for row in followed if row.channel_id in CHANNELS]
    followed_items = []
    for item, source in candidates:
        reasons = [{"rule": "watched_topic", "label": f"关注主题：{topic.name}"} for topic in topics if matches(item, [topic.name] + list(topic.keywords or []))]
        for channel in followed_channels:
            key = channel["id"]
            if key == "all" or matches(item, CHANNELS[key][1]) or (key == "papers" and item.content_type == "paper") or (key == "open-source" and item.content_type == "repository"):
                reasons.append({"rule": "followed_channel", "label": f"关注频道：{channel['name']}"})
        if reasons:
            followed_items.append(content_dict(item, source, reasons=reasons))
        if len(followed_items) >= 12:
            break
    recommendation = await discover_data(db, user_id, "all", "week", 1, 5)
    favorite_rows = (await db.scalars(select(Favorite).where(Favorite.user_id == user_id).order_by(Favorite.created_at.desc()).limit(8))).all()
    favorites = await saved_targets(db, user_id, favorite_rows)
    for item, row in zip(favorites, favorite_rows):
        item["created_at"] = dt(row.created_at)
    view_rows = (await db.scalars(select(RecentView).where(RecentView.user_id == user_id).order_by(RecentView.viewed_at.desc(), RecentView.id.desc()).limit(8))).all()
    views = await saved_targets(db, user_id, view_rows)
    for item, row in zip(views, view_rows):
        item["viewed_at"] = dt(row.viewed_at)
    reports = (await db.scalars(
        select(Report).where(Report.user_id == user_id, Report.deleted_at.is_(None))
        .order_by(Report.updated_at.desc(), Report.id.desc()).limit(8)
    )).all()
    recent_reports = [dict(id=row.id, title=row.title, report_type=row.report_type, kind="report", path=f"/reports/{row.id}",
                           status=row.status, updated_at=dt(row.updated_at)) for row in reports]
    histories = (await db.scalars(select(AnalysisHistory).where(
        AnalysisHistory.user_id == user_id, AnalysisHistory.module.in_(["insight", "mouthpiece", "timeline"]),
        AnalysisHistory.status == "completed").order_by(AnalysisHistory.created_at.desc(), AnalysisHistory.id.desc()).limit(8))).all()
    recent_reports.extend(dict(id=row.id, title=history_title(row), report_type=row.module, kind="history",
        path=f"/history?record={row.id}", status=row.status, updated_at=dt(row.created_at)) for row in histories)
    recent_reports = sorted(recent_reports, key=lambda row: (row["updated_at"], row["id"]), reverse=True)[:8]
    return {"date": datetime.now(timezone.utc).date().isoformat(), "attention": attention, "followed_channels": followed_channels, "followed_items": followed_items, "recommendations": recommendation["items"], "favorites": favorites, "recent_reports": recent_reports, "recent_views": views, "tasks": [], "source_warnings": recommendation["source_warnings"]}
