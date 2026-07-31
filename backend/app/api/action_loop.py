from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies import get_current_user, get_tenant_context
from app.models.action_loop import *
from app.models.global_intelligence import DecisionRoom
from app.models.intelligence import ContentItem
from app.models.user import User
from app.schemas.action_loop import *
from app.services.enterprise import TenantContext, require_permission
from app.services.action_loop import valid_evidence, serialize, create_run
router = APIRouter(prefix="/api/v1", tags=["Action loop"])
def fail(msg, code=400): raise HTTPException(code, msg)
async def get_action(db, ctx, aid):
    x = await db.scalar(select(ResponseAction).where(ResponseAction.id == aid, ResponseAction.organization_id == ctx.organization.id))
    if not x: fail("Action not found", 404)
    return x
@router.get("/actions")
async def actions(ctx:TenantContext=Depends(get_tenant_context), db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"action.read"); return [serialize(x) for x in (await db.scalars(select(ResponseAction).where(ResponseAction.organization_id==ctx.organization.id).order_by(ResponseAction.created_at.desc()).limit(100))).all()]
@router.post("/actions", status_code=201)
async def create(p:ActionCreate, ctx:TenantContext=Depends(get_tenant_context), user:User=Depends(get_current_user), db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"action.write")
    if not (p.event_id or p.scenario_id or p.decision_room_id): fail("Action must link an event, scenario, or decision room")
    if p.decision_room_id:
        room=await db.scalar(select(DecisionRoom).where(DecisionRoom.id==p.decision_room_id,DecisionRoom.organization_id==ctx.organization.id));
        if not room: fail("Decision room not found",404)
    try: evidence=await valid_evidence(db,ctx.organization.id,p.evidence_content_ids)
    except ValueError as e: fail(str(e),422)
    x=ResponseAction(organization_id=ctx.organization.id,workspace_id=ctx.workspace.id if ctx.workspace else None,created_by=user.id,owner_id=p.owner_id,event_id=p.event_id,scenario_id=p.scenario_id,decision_room_id=p.decision_room_id,title=p.title,description=p.description,evidence_content_ids=evidence,risk_level=p.risk_level,due_at=p.due_at,sla_minutes=p.sla_minutes,budget_cents=p.budget_cents,stop_conditions=p.stop_conditions,dependency_ids=p.dependency_ids,status="pending_approval" if p.risk_level=="high" else "draft"); db.add(x); await db.flush(); return serialize(x)
@router.get("/actions/{aid}")
async def detail(aid:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"action.read"); a=await get_action(db,ctx,aid); steps=(await db.scalars(select(ActionStep).where(ActionStep.action_id==aid).order_by(ActionStep.sequence))).all(); runs=(await db.scalars(select(ActionRun).where(ActionRun.action_id==aid).order_by(ActionRun.started_at.desc()))).all(); receipts=(await db.scalars(select(ActionReceipt).where(ActionReceipt.action_id==aid).order_by(ActionReceipt.received_at.desc()))).all(); return {**serialize(a),"steps":[s.__dict__ for s in steps],"runs":[r.__dict__ for r in runs],"receipts":[r.__dict__ for r in receipts]}
@router.post("/actions/{aid}/steps",status_code=201)
async def step(aid:str,p:StepCreate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"action.write"); a=await get_action(db,ctx,aid); x=ActionStep(organization_id=ctx.organization.id,action_id=a.id,**p.model_dump()); db.add(x); await db.flush(); return {"id":x.id,"status":x.status}
@router.post("/actions/{aid}/approve")
async def approve(aid:str,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"action.approve"); a=await get_action(db,ctx,aid)
    if a.created_by==user.id: fail("Creator cannot approve their own action",403)
    if a.status!="pending_approval": fail("Action is not awaiting approval",409)
    a.status="approved"; a.approved_by=user.id; return serialize(a)
@router.post("/actions/{aid}/start")
async def start(aid:str,idempotency_key:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"action.execute"); a=await get_action(db,ctx,aid)
    if a.risk_level=="high" and a.status!="approved": fail("High-risk action requires approval",409)
    try: run,new=await create_run(db,a,idempotency_key)
    except ValueError as e: fail(str(e),409)
    return {"run_id":run.id,"created":new,"status":run.status}
@router.post("/actions/{aid}/receipts",status_code=201)
async def receipt(aid:str,p:ReceiptCreate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"action.execute"); a=await get_action(db,ctx,aid)
    try: ev=await valid_evidence(db,ctx.organization.id,p.evidence_content_ids)
    except ValueError as e: fail(str(e),422)
    x=ActionReceipt(organization_id=ctx.organization.id,action_id=aid,evidence_content_ids=ev,**p.model_dump()); db.add(x); await db.flush(); return {"id":x.id,"evidence_content_ids":ev}
@router.post("/actions/{aid}/impact",status_code=201)
async def impact(aid:str,p:ImpactCreate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"action.write"); await get_action(db,ctx,aid)
    try: ev=await valid_evidence(db,ctx.organization.id,p.source_content_ids)
    except ValueError as e: fail(str(e),422)
    x=ImpactMeasurement(organization_id=ctx.organization.id,action_id=aid,source_content_ids=ev,**p.model_dump(exclude={"source_content_ids"})); db.add(x); await db.flush(); return {"id":x.id,"attribution_boundary":x.attribution_boundary,"source_content_ids":ev}
@router.get("/actions/{aid}/impact")
async def impacts(aid:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"action.read"); await get_action(db,ctx,aid); return [{"id":x.id,"metric_id":x.metric_id,"before_value":x.before_value,"after_value":x.after_value,"attribution_confidence":x.attribution_confidence,"attribution_boundary":x.attribution_boundary,"source_content_ids":x.source_content_ids} for x in (await db.scalars(select(ImpactMeasurement).where(ImpactMeasurement.action_id==aid))).all()]
@router.post("/impact/metrics",status_code=201)
async def metric(p:ImpactMetricCreate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"action.manage"); x=ImpactMetricDefinition(organization_id=ctx.organization.id,**p.model_dump()); db.add(x); await db.flush(); return {"id":x.id,**p.model_dump()}
@router.get("/action-dashboard")
async def dashboard(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"action.read"); rows=(await db.scalars(select(ResponseAction).where(ResponseAction.organization_id==ctx.organization.id))).all(); return {"total":len(rows),"by_status":{s:sum(x.status==s for x in rows) for s in {x.status for x in rows}},"budget_cents":sum(x.budget_cents for x in rows),"spent_cents":sum(x.spent_cents for x in rows),"empty":not rows}
