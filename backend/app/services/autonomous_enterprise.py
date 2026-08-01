import hashlib,json,math
from datetime import datetime,timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.autonomous_enterprise import *
from app.models.commercialization import ApprovalFlow
def digest(value)->str:return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
def view(row):return {c.name:getattr(row,c.name) for c in row.__table__.columns if c.name not in {"secret_reference"}}
async def start_approval(db:AsyncSession,org_id:str,user_id:str,p)->ApprovalRun:
 old=await db.scalar(select(ApprovalRun).where(ApprovalRun.organization_id==org_id,ApprovalRun.idempotency_key==p.idempotency_key));
 if old:return old
 flow=await db.scalar(select(ApprovalFlow).where(ApprovalFlow.id==p.flow_id,ApprovalFlow.organization_id==org_id,ApprovalFlow.enabled.is_(True)))
 if not flow:raise HTTPException(404,"Approval flow not found")
 run=ApprovalRun(organization_id=org_id,flow_id=flow.id,subject_type=p.subject_type,subject_id=p.subject_id,idempotency_key=p.idempotency_key,context=p.context,signature_chain=[],compensation_log=[],started_by=user_id);db.add(run);await db.flush()
 for node in flow.graph.get("nodes",[]):
  db.add(ApprovalNodeRun(organization_id=org_id,run_id=run.id,node_id=node["id"],node_type=node.get("type","approval"),status="ready" if not flow.graph.get("edges") or not any(e.get("to")==node["id"] for e in flow.graph["edges"]) else "pending",assignee_id=node.get("assignee_id")))
 await db.flush();return run
async def decide_node(db:AsyncSession,org_id:str,user_id:str,run_id:str,p)->ApprovalRun:
 run=await db.scalar(select(ApprovalRun).where(ApprovalRun.id==run_id,ApprovalRun.organization_id==org_id).with_for_update());node=await db.scalar(select(ApprovalNodeRun).where(ApprovalNodeRun.run_id==run_id,ApprovalNodeRun.node_id==p.node_id,ApprovalNodeRun.organization_id==org_id))
 if not run or not node:raise HTTPException(404,"Approval run or node not found")
 if node.status not in {"ready","delegated"}:raise HTTPException(409,"Approval node is not actionable")
 if p.delegate_to_id:node.delegated_to_id=p.delegate_to_id;node.status="delegated";return run
 signature=digest({"run":run.id,"node":node.node_id,"decision":p.decision,"actor":user_id,"nonce":p.signature_nonce});node.decision=p.decision;node.signature=signature;node.status="completed";node.completed_at=datetime.now(timezone.utc);run.signature_chain=[*run.signature_chain,{"node":node.node_id,"actor":user_id,"decision":p.decision,"signature":signature}]
 if p.decision=="rejected":run.status="compensating";run.compensation_log=[*run.compensation_log,{"reason":"rejected","node":node.node_id,"status":"scheduled"}]
 else:
  pending=await db.scalar(select(ApprovalNodeRun.id).where(ApprovalNodeRun.run_id==run.id,ApprovalNodeRun.status.in_(["pending","ready","delegated"]),ApprovalNodeRun.id!=node.id));
  if not pending:run.status="completed";run.finished_at=datetime.now(timezone.utc)
 await db.flush();return run
async def spend_privacy(db:AsyncSession,org_id:str,user_id:str,p):
 budget=await db.scalar(select(PrivacyBudget).where(PrivacyBudget.organization_id==org_id,PrivacyBudget.dataset_key==p.dataset_key,PrivacyBudget.status=="active").order_by(PrivacyBudget.period.desc()).with_for_update())
 if not budget:raise HTTPException(404,"Privacy budget not found")
 risk=min(1.0,p.similar_query_count/10)
 status="blocked" if p.cohort_size<budget.minimum_cohort or risk>=.8 or budget.epsilon_used+p.epsilon_cost>budget.epsilon_limit else "approved"
 audit=PrivacyQueryAudit(organization_id=org_id,budget_id=budget.id,query_fingerprint=digest(p.query),epsilon_cost=p.epsilon_cost,cohort_size=p.cohort_size,attack_risk=risk,status=status,created_by=user_id);db.add(audit)
 if status=="blocked":await db.flush();raise HTTPException(429,"Privacy query blocked by cohort, attack-risk, or epsilon budget")
 budget.epsilon_used+=p.epsilon_cost;await db.flush();return audit
def simulate_policy(rules:dict,tests:list[dict])->dict:
 passed=0;failures=[]
 for i,t in enumerate(tests):
  actual=all(t.get("input",{}).get(k)==v for k,v in rules.get("match",{}).items());expected=bool(t.get("allow"));passed+=actual==expected
  if actual!=expected:failures.append(i)
 return {"passed":passed,"total":len(tests),"failures":failures,"ready":bool(tests) and not failures}
def causal_effect(treatment:dict,control:dict)->float:
 return (float(treatment["after"])-float(treatment["before"]))-(float(control["after"])-float(control["before"]))
def forecast_cost(values:list[int])->dict:
 if not values:return {"forecast_cents":0,"anomaly":False}
 avg=sum(values)/len(values);variance=sum((x-avg)**2 for x in values)/len(values);return {"forecast_cents":round(avg*1.1),"anomaly":values[-1]>avg+2*math.sqrt(variance) if len(values)>2 else False}
