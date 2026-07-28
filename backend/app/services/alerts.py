import hashlib
from datetime import datetime,timezone
from sqlalchemy import func,select
from app.models.intelligence import AlertAction,AlertIncident,AlertReplayRun,AlertRule,AuditLog,ContentItem,DataSource,Event,EventContent,PropagationNode
from app.services.automation import create_notification
def now():return datetime.now(timezone.utc)
async def context(db,event):
 rows=(await db.execute(select(ContentItem,DataSource).join(EventContent,EventContent.content_item_id==ContentItem.id).join(DataSource,DataSource.id==ContentItem.source_id).where(EventContent.event_id==event.id,ContentItem.deleted_at.is_(None)))).all();nodes=(await db.scalars(select(PropagationNode).where(PropagationNode.event_id==event.id).order_by(PropagationNode.occurred_at))).all();return rows,nodes
def condition_match(kind,cfg,event,rows,nodes):
 text="\n".join(f"{x.title}\n{x.body}" for x,_ in rows).casefold();reasons=[];evidence=[]
 if kind=="keyword":
  words=[str(x).casefold() for x in cfg.get("keywords",[]) if str(x).strip()];hit=[x for x in words if x in text];ok=bool(hit);reasons.append("命中关键词："+"、".join(hit));evidence=[x.id for x,_ in rows if any(w in f"{x.title} {x.body}".casefold() for w in hit)]
 elif kind=="heat":ok=event.heat_score>=float(cfg.get("min",70));reasons.append(f"事件热度 {event.heat_score:.1f}")
 elif kind=="ai_risk":ok=event.risk_score>=float(cfg.get("min",60));reasons.append(f"AI 风险评分 {event.risk_score:.1f}")
 elif kind=="negative":evidence=[x.id for x,_ in rows if x.sentiment=="negative"];ratio=len(evidence)/len(rows) if rows else 0;ok=ratio>=float(cfg.get("ratio",.4));reasons.append(f"负面内容占比 {ratio:.0%}")
 elif kind=="media":keys={str(x).casefold() for x in cfg.get("sources",[])};evidence=[x.id for x,s in rows if s.key.casefold() in keys or s.name.casefold() in keys];ok=bool(evidence);reasons.append(f"指定媒体命中 {len(evidence)} 条")
 elif kind=="official":evidence=[x.id for x,_ in rows if x.is_official];ok=len(evidence)>=int(cfg.get("min_count",1));reasons.append(f"官方内容 {len(evidence)} 条")
 elif kind=="velocity":
  valid=[n for n in nodes if n.occurred_at];hours=max(((valid[-1].occurred_at-valid[0].occurred_at).total_seconds()/3600),1/60) if len(valid)>1 else 0;rate=(len(valid)-1)/hours if hours else 0;ok=rate>=float(cfg.get("per_hour",5));reasons.append(f"传播速度 {rate:.1f} 节点/小时");evidence=[n.content_item_id for n in valid]
 else:ok=False;reasons.append("未知规则类型")
 return ok,reasons[0],list(dict.fromkeys(evidence))[:20]
async def evaluate(db,rule,event):
 rows,nodes=await context(db,event);conditions=rule.config.get("conditions",[]) if rule.rule_type=="composite" else [{"type":rule.rule_type,**rule.config}];checks=[condition_match(c.get("type",""),c,event,rows,nodes) for c in conditions];matched=(all(x[0] for x in checks) if rule.combinator=="all" else any(x[0] for x in checks)) if checks else False;return matched,"；".join(x[1] for x in checks),list(dict.fromkeys(i for x in checks for i in x[2]))
async def scan_rule(db,rule,from_at=None,to_at=None,create=True):
 q=select(Event).where(Event.deleted_at.is_(None));q=q.where(Event.last_activity_at>=from_at) if from_at else q;q=q.where(Event.last_activity_at<=to_at) if to_at else q;events=(await db.scalars(q.order_by(Event.last_activity_at.desc()).limit(500))).all();matches=[]
 for event in events:
  ok,reason,evidence=await evaluate(db,rule,event)
  if not ok:continue
  matches.append({"event_id":event.id,"title":event.title,"reason":reason,"evidence_content_ids":evidence})
  if create:
   fingerprint=hashlib.sha256(f"{rule.id}:{event.id}:{reason}".encode()).hexdigest();existing=await db.scalar(select(AlertIncident).where(AlertIncident.rule_id==rule.id,AlertIncident.event_id==event.id,AlertIncident.fingerprint==fingerprint))
   if not existing:
    incident=AlertIncident(rule_id=rule.id,user_id=rule.user_id,event_id=event.id,status="triggered",severity=rule.severity,title=f"{rule.name}：{event.title}"[:300],reason=reason,evidence=evidence,fingerprint=fingerprint,assignee_id=rule.assignee_id);db.add(incident);await db.flush();await create_notification(db,rule.user_id,"alert",incident.title,reason,severity=rule.severity,group_key=f"alert:{rule.id}",payload={"incident_id":incident.id,"event_id":event.id})
 return matches
async def replay(db,rule,user_id,from_at,to_at):
 if from_at>=to_at:raise ValueError("回放开始时间必须早于结束时间")
 matches=await scan_rule(db,rule,from_at,to_at,False);run=AlertReplayRun(rule_id=rule.id,user_id=user_id,from_at=from_at,to_at=to_at,matched_count=len(matches),sample_results=matches[:50]);db.add(run);await db.flush();return run
STATES={"assign":None,"acknowledge":"acknowledged","resolve":"resolved","close":"closed","reopen":"triggered","false_positive":"closed"}
async def act(db,incident,user_id,action,assignee_id,note):
 before=incident.status
 if action=="assign":incident.assignee_id=assignee_id;after=before
 else:after=STATES[action];incident.status=after
 if action=="acknowledge":incident.acknowledged_at=now()
 if action in {"close","false_positive"}:incident.closed_at=now()
 if action=="false_positive":incident.is_false_positive=True
 db.add(AlertAction(incident_id=incident.id,user_id=user_id,action=action,note=note,before_status=before,after_status=after));db.add(AuditLog(user_id=user_id,action=f"alert.{action}",target_type="alert_incident",target_id=incident.id,before_data={"status":before},after_data={"status":after,"assignee_id":incident.assignee_id,"note":note}));return incident
