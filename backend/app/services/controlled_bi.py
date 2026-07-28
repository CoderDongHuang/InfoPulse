import re
from datetime import datetime,timedelta,timezone
from sqlalchemy import func,select
from app.models.intelligence import BIQueryHistory,ContentItem,DataSource,Event
METRICS={"content_count":{"label":"采集内容数","definition":"时间范围内未删除内容数量"},"event_count":{"label":"事件数","definition":"时间范围内未删除事件数量"},"risk_events":{"label":"风险事件数","definition":"风险评分不低于 60 的事件数量"},"avg_heat":{"label":"平均热度","definition":"事件热度评分算术平均值"},"avg_risk":{"label":"平均风险","definition":"事件风险评分算术平均值"}}
DIMENSIONS={"day":{"label":"日期"},"source":{"label":"数据来源"},"category":{"label":"事件类别"},"sentiment":{"label":"情感"},"status":{"label":"事件状态"}}
def plan(question):
 q=question.casefold();days=90 if "90" in q or "季度" in q else 30 if "30" in q or "月" in q else 7;metric="risk_events" if "风险事件" in q else "avg_risk" if "平均风险" in q else "avg_heat" if "平均热" in q else "event_count" if "事件" in q else "content_count";dimension="source" if "来源" in q or "媒体" in q else "category" if "类别" in q or "行业" in q else "sentiment" if "情感" in q or "负面" in q else "status" if "状态" in q else "day";chart="line" if dimension=="day" else "bar";return {"metric":metric,"dimension":dimension,"days":days,"chart":chart,"filters":{}}
async def execute(db,user_id,question):
 p=plan(question);start=datetime.now(timezone.utc)-timedelta(days=p["days"]);metric,dimension=p["metric"],p["dimension"]
 event_metric=metric in {"event_count","risk_events","avg_heat","avg_risk"}
 if event_metric:
  dim={"day":func.date(Event.last_activity_at),"category":Event.category,"status":Event.status}.get(dimension,func.date(Event.last_activity_at));value=func.count(Event.id) if metric in {"event_count","risk_events"} else func.avg(Event.heat_score if metric=="avg_heat" else Event.risk_score);conds=[Event.deleted_at.is_(None),Event.last_activity_at>=start];conds.append(Event.risk_score>=60) if metric=="risk_events" else None;rows=(await db.execute(select(dim.label("dimension"),value.label("value")).where(*conds).group_by(dim).order_by(dim))).all()
 else:
  if dimension=="source":dim=DataSource.name;stmt=select(dim.label("dimension"),func.count(ContentItem.id).label("value")).join(DataSource,DataSource.id==ContentItem.source_id)
  else:dim=ContentItem.sentiment if dimension=="sentiment" else func.date(ContentItem.published_at);stmt=select(dim.label("dimension"),func.count(ContentItem.id).label("value"))
  rows=(await db.execute(stmt.where(ContentItem.deleted_at.is_(None),ContentItem.published_at>=start).group_by(dim).order_by(dim))).all()
 data=[{"dimension":str(d or "未知"),"value":round(float(v or 0),2)} for d,v in rows];result={"chart":p["chart"],"series":data,"metric":{"key":metric,**METRICS[metric]},"dimension":{"key":dimension,**DIMENSIONS[dimension]},"range":{"from":start.isoformat(),"to":datetime.now(timezone.utc).isoformat(),"days":p["days"]},"explanation":f"按{DIMENSIONS[dimension]['label']}聚合{METRICS[metric]['label']}。"};history=BIQueryHistory(user_id=user_id,question=question,query_plan=p,result=result);db.add(history);await db.flush();return history,result
