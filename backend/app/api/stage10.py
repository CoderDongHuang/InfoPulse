from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import func,select
from app.core.database import get_db
from app.dependencies import get_current_user,require_admin
from app.models.user import User
from app.models.intelligence import AgentMessage,AgentTask,AlertAction,AlertIncident,AlertReplayRun,AlertRule,Analysis,AuditLog,BIQueryHistory,DataSource,DeliveryAttempt,ModelUsage,SyncRun,TaskRun
from app.schemas.stage10 import BIQuestion,IncidentActionRequest,ReplayRequest,RuleCreate,RuleUpdate
from app.services.alerts import act,replay,scan_rule
from app.services.controlled_bi import DIMENSIONS,METRICS,execute
router=APIRouter(prefix="/api/v1",tags=["Alerts, Controlled BI and Admin"])
TYPES={"keyword","heat","negative","media","official","velocity","ai_risk"}
def validate_config(rule_type,config):
 conditions=config.get("conditions",[]) if rule_type=="composite" else [{"type":rule_type,**config}]
 if not conditions or any(x.get("type") not in TYPES for x in conditions):raise HTTPException(422,"规则条件类型不受支持")
 if any(x.get("type")=="keyword" and not x.get("keywords") for x in conditions):raise HTTPException(422,"关键词规则至少需要一个关键词")
def rule_json(x):return {"id":x.id,"name":x.name,"rule_type":x.rule_type,"config":x.config,"combinator":x.combinator,"severity":x.severity,"enabled":x.enabled,"assignee_id":x.assignee_id,"created_at":x.created_at,"updated_at":x.updated_at}
def incident_json(x):return {"id":x.id,"rule_id":x.rule_id,"event_id":x.event_id,"status":x.status,"severity":x.severity,"title":x.title,"reason":x.reason,"evidence":x.evidence,"assignee_id":x.assignee_id,"is_false_positive":x.is_false_positive,"triggered_at":x.triggered_at,"acknowledged_at":x.acknowledged_at,"closed_at":x.closed_at}
async def owned_rule(db,rid,uid):
 x=await db.scalar(select(AlertRule).where(AlertRule.id==rid,AlertRule.user_id==uid))
 if not x:raise HTTPException(404,"预警规则不存在")
 return x
async def owned_incident(db,iid,uid):
 x=await db.scalar(select(AlertIncident).where(AlertIncident.id==iid,AlertIncident.user_id==uid))
 if not x:raise HTTPException(404,"预警不存在")
 return x
@router.get("/alert-rules")
async def rules(user:User=Depends(get_current_user),db=Depends(get_db)):return [rule_json(x) for x in (await db.scalars(select(AlertRule).where(AlertRule.user_id==user.id).order_by(AlertRule.updated_at.desc()))).all()]
@router.post("/alert-rules",status_code=201)
async def create_rule(p:RuleCreate,user:User=Depends(get_current_user),db=Depends(get_db)):validate_config(p.rule_type,p.config);x=AlertRule(user_id=user.id,**p.model_dump());db.add(x);await db.flush();db.add(AuditLog(user_id=user.id,action="alert_rule.create",target_type="alert_rule",target_id=x.id,before_data={},after_data=p.model_dump(mode="json")));return rule_json(x)
@router.patch("/alert-rules/{rid}")
async def update_rule(rid:str,p:RuleUpdate,user:User=Depends(get_current_user),db=Depends(get_db)):
 x=await owned_rule(db,rid,user.id);before=rule_json(x);changes=p.model_dump(exclude_none=True);validate_config(x.rule_type,changes.get("config",x.config))
 for k,v in changes.items():setattr(x,k,v)
 db.add(AuditLog(user_id=user.id,action="alert_rule.update",target_type="alert_rule",target_id=x.id,before_data=before,after_data=changes));return rule_json(x)
@router.delete("/alert-rules/{rid}",status_code=204)
async def delete_rule(rid:str,user:User=Depends(get_current_user),db=Depends(get_db)):await db.delete(await owned_rule(db,rid,user.id))
@router.post("/alert-rules/{rid}/run")
async def run_rule(rid:str,user:User=Depends(get_current_user),db=Depends(get_db)):x=await owned_rule(db,rid,user.id);matches=await scan_rule(db,x);return {"matched_count":len(matches),"items":matches[:50]}
@router.post("/alert-rules/{rid}/replay")
async def replay_rule(rid:str,p:ReplayRequest,user:User=Depends(get_current_user),db=Depends(get_db)):
 try:x=await replay(db,await owned_rule(db,rid,user.id),user.id,p.from_at,p.to_at)
 except ValueError as e:raise HTTPException(422,str(e))
 return {"id":x.id,"matched_count":x.matched_count,"sample_results":x.sample_results,"from_at":x.from_at,"to_at":x.to_at}
@router.get("/alert-rules/{rid}/replays")
async def replays(rid:str,user:User=Depends(get_current_user),db=Depends(get_db)):await owned_rule(db,rid,user.id);return [{"id":x.id,"matched_count":x.matched_count,"sample_results":x.sample_results,"from_at":x.from_at,"to_at":x.to_at,"created_at":x.created_at} for x in (await db.scalars(select(AlertReplayRun).where(AlertReplayRun.rule_id==rid,AlertReplayRun.user_id==user.id).order_by(AlertReplayRun.created_at.desc()))).all()]
@router.get("/alerts")
async def incidents(status:str|None=None,user:User=Depends(get_current_user),db=Depends(get_db)):
 q=select(AlertIncident).where(AlertIncident.user_id==user.id);q=q.where(AlertIncident.status==status) if status else q;return [incident_json(x) for x in (await db.scalars(q.order_by(AlertIncident.triggered_at.desc()).limit(200))).all()]
@router.get("/alerts/{iid}")
async def incident(iid:str,user:User=Depends(get_current_user),db=Depends(get_db)):
 x=await owned_incident(db,iid,user.id);actions=(await db.scalars(select(AlertAction).where(AlertAction.incident_id==iid).order_by(AlertAction.created_at))).all();return {**incident_json(x),"actions":[{"id":a.id,"action":a.action,"note":a.note,"before_status":a.before_status,"after_status":a.after_status,"created_at":a.created_at,"user_id":a.user_id} for a in actions]}
@router.post("/alerts/{iid}/actions")
async def incident_action(iid:str,p:IncidentActionRequest,user:User=Depends(get_current_user),db=Depends(get_db)):return incident_json(await act(db,await owned_incident(db,iid,user.id),user.id,p.action,p.assignee_id,p.note))
@router.get("/bi/capabilities")
async def bi_capabilities(_u:User=Depends(get_current_user)):return {"metrics":METRICS,"dimensions":DIMENSIONS,"sql_allowed":False,"max_days":90}
@router.post("/bi/query")
async def bi_query(p:BIQuestion,user:User=Depends(get_current_user),db=Depends(get_db)):history,result=await execute(db,user.id,p.question);return {"id":history.id,"question":p.question,"plan":history.query_plan,**result}
@router.get("/bi/history")
async def bi_history(user:User=Depends(get_current_user),db=Depends(get_db)):return [{"id":x.id,"question":x.question,"plan":x.query_plan,"result":x.result,"created_at":x.created_at} for x in (await db.scalars(select(BIQueryHistory).where(BIQueryHistory.user_id==user.id).order_by(BIQueryHistory.created_at.desc()).limit(100))).all()]
@router.get("/admin/source-health")
async def source_health(_u:User=Depends(require_admin),db=Depends(get_db)):return [{"id":x.id,"name":x.name,"type":x.source_type,"status":x.health_status,"last_success_at":x.last_success_at,"last_error":bool(x.last_error),"enabled":x.enabled} for x in (await db.scalars(select(DataSource).order_by(DataSource.name))).all()]
@router.get("/admin/task-health")
async def task_health(_u:User=Depends(require_admin),db=Depends(get_db)):return {"tasks":{s:int(c) for s,c in (await db.execute(select(AgentTask.status,func.count()).group_by(AgentTask.status))).all()},"runs":{s:int(c) for s,c in (await db.execute(select(TaskRun.status,func.count()).group_by(TaskRun.status))).all()},"failed_deliveries":int(await db.scalar(select(func.count()).select_from(DeliveryAttempt).where(DeliveryAttempt.status.in_(["failed","dead_letter"]))) or 0)}
@router.get("/admin/model-usage")
async def model_usage(_u:User=Depends(require_admin),db=Depends(get_db)):
 tracked=(await db.execute(select(ModelUsage.model_name,ModelUsage.feature,func.sum(ModelUsage.prompt_tokens),func.sum(ModelUsage.completion_tokens),func.sum(ModelUsage.cost)).group_by(ModelUsage.model_name,ModelUsage.feature))).all();analyses=(await db.execute(select(Analysis.model_name,func.count()).where(Analysis.model_name!="").group_by(Analysis.model_name))).all();messages=(await db.execute(select(AgentMessage.model_name,func.count()).where(AgentMessage.model_name!="").group_by(AgentMessage.model_name))).all();return {"usage":[{"model":m,"feature":f,"prompt_tokens":int(p or 0),"completion_tokens":int(c or 0),"cost":round(float(cost or 0),4)} for m,f,p,c,cost in tracked],"generated_objects":{"analyses":{m:int(c) for m,c in analyses},"agent_messages":{m:int(c) for m,c in messages}},"note":"历史对象未记录 token 时仅统计生成次数"}
@router.get("/admin/audit-logs")
async def admin_audits(limit:int=Query(100,ge=1,le=500),_u:User=Depends(require_admin),db=Depends(get_db)):return [{"id":x.id,"actor_id":x.user_id,"action":x.action,"target_type":x.target_type,"target_id":x.target_id,"created_at":x.created_at} for x in (await db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))).all()]
