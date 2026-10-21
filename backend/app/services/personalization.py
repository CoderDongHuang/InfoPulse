"""Resolve saved targets without exposing deleted or another user's reports."""
from sqlalchemy import select
from app.models.intelligence import ContentItem, DataSource, Event, Report
from app.models.analysis_history import AnalysisHistory


def history_title(row):
    output, params = row.output_result or {}, row.input_params or {}
    if row.module == "mouthpiece":
        return output.get("title") or str(params.get("source_text") or "")[:30] or "未命名文案"
    return output.get("topic") or params.get("keyword") or params.get("topic") or "未命名记录"


async def saved_targets(db, user_id, favorites):
    targets = {}
    ids = [row.target_id for row in favorites if row.target_type == "content"]
    if ids:
        rows = (await db.execute(select(ContentItem, DataSource).join(DataSource).where(
            ContentItem.id.in_(ids), ContentItem.deleted_at.is_(None)))).all()
        for item, source in rows:
            targets[("content", item.id)] = dict(title=item.title, summary=(item.body or "")[:240],
                source_name=source.name, canonical_url=item.canonical_url, path=None, available=True)
    for kind, model, conditions in (
        ("event", Event, [Event.deleted_at.is_(None)]),
        ("report", Report, [Report.deleted_at.is_(None), Report.user_id == user_id]),
    ):
        ids = [row.target_id for row in favorites if row.target_type == kind]
        if ids:
            rows = (await db.scalars(select(model).where(model.id.in_(ids), *conditions))).all()
            for row in rows:
                targets[(kind, row.id)] = dict(title=row.title, summary=getattr(row, "summary", "")[:240],
                    source_name="事件" if kind == "event" else "我的报告", canonical_url=None,
                    path=f"/{'events' if kind == 'event' else 'reports'}/{row.id}", available=True)
    ids = [row.target_id for row in favorites if row.target_type == "history"]
    if ids:
        rows = (await db.scalars(select(AnalysisHistory).where(
            AnalysisHistory.id.in_(ids), AnalysisHistory.user_id == user_id))).all()
        for row in rows:
            output = row.output_result or {}
            targets[("history", row.id)] = dict(title=history_title(row),
                summary=str(output.get("body") or output.get("overview") or output.get("summary") or "")[:240],
                source_name={"insight": "热点洞察", "mouthpiece": "表达文案", "timeline": "事件脉络"}.get(row.module, "内容档案"),
                canonical_url=None, path=f"/history?record={row.id}", available=True)
    return [{"target_type": row.target_type, "target_id": row.target_id, **targets.get(
        (row.target_type, row.target_id), dict(title="内容已删除或暂不可访问", summary="", source_name="不可用",
            canonical_url=None, path=None, available=False))} for row in favorites]
