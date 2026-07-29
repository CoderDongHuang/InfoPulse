"""Tenant agent orchestration, governance, evaluations and template API."""
import secrets
from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import func,or_,select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user,get_tenant_context
from app.models.orchestration import AgentMemory,EvaluationDataset,EvaluationRun,ModelRoute,OrchestrationAudit,PromptDefinition,ToolDefinition,ToolPolicy,Workflow,WorkflowApproval,WorkflowRun,WorkflowStepRun,WorkflowTemplate,WorkflowVersion
from app.models.user import User
from app.schemas.orchestration import ApprovalDecision,DatasetCreate,MemoryPut,PolicyUpsert,PromptCreate,RouteUpsert,RunCreate,TemplateCreate,ToolCreate,WorkflowCreate,WorkflowVersionCreate
from app.services.enterprise import TenantContext,require_permission
from app.services.orchestration import audit,evaluate,execute_one,seed_catalog,validate_graph

router=APIRouter(prefix="/api/v1/orchestration",tags=["Agent Orchestration"])
def utc():return datetime.now(timezone.utc)
def check_workspace(ctx,wid):
    if wid and (not ctx.workspace or ctx.workspace.id!=wid):raise HTTPException(403,"Select the target workspace in tenant context")
async def workflow_owned(db,ctx,wid):
    row=await db.get(Workflow,wid)
    if not row or row.organization_id!=ctx.organization.id:raise HTTPException(404,"Workflow not found")
    return row
def workflow_view(x):return {"id":x.id,"name":x.name,"description":x.description,"workspace_id":x.workspace_id,"status":x.status,"active_version_id":x.active_version_id,"created_at":x.created_at}

@router.get("/overview")
async def overview(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.read");data={}
    for key,model in (("workflows",Workflow),("runs",WorkflowRun),("pending_approvals",WorkflowApproval),("tools",ToolDefinition)):
        q=select(func.count()).select_from(model).where(model.organization_id==ctx.organization.id)
        if model is WorkflowApproval:q=q.where(model.status=="pending")
        data[key]=int(await db.scalar(q) or 0)
    data["running"]=int(await db.scalar(select(func.count()).select_from(WorkflowRun).where(WorkflowRun.organization_id==ctx.organization.id,WorkflowRun.status.in_(["queued","running","waiting_approval"]))) or 0);return data

@router.get("/tools")
async def tools(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.read");await seed_catalog(db,ctx.organization.id);rows=(await db.scalars(select(ToolDefinition).where(ToolDefinition.organization_id==ctx.organization.id).order_by(ToolDefinition.key))).all()
    policies=(await db.scalars(select(ToolPolicy).where(ToolPolicy.organization_id==ctx.organization.id))).all();by={x.tool_id:x for x in policies}
    return [{"id":x.id,"key":x.key,"name":x.name,"description":x.description,"risk_level":x.risk_level,"connector_key":x.connector_key,"action":x.action,"enabled":x.enabled,"policy":{"effect":by[x.id].effect,"require_approval":by[x.id].require_approval,"max_calls_per_run":by[x.id].max_calls_per_run,"workspace_id":by[x.id].workspace_id} if x.id in by else None} for x in rows]

@router.post("/tools",status_code=201)
async def create_tool(p:ToolCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.manage");row=ToolDefinition(organization_id=ctx.organization.id,**p.model_dump());db.add(row);await db.flush();audit(db,ctx.organization.id,"tool.created",actor_id=user.id,details={"key":row.key,"risk":row.risk_level});return {"id":row.id,"key":row.key}

@router.put("/tool-policies")
async def policy(p:PolicyUpsert,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.manage");check_workspace(ctx,p.workspace_id);tool=await db.get(ToolDefinition,p.tool_id)
    if not tool or tool.organization_id!=ctx.organization.id:raise HTTPException(404,"Tool not found")
    row=await db.scalar(select(ToolPolicy).where(ToolPolicy.organization_id==ctx.organization.id,ToolPolicy.workspace_id==p.workspace_id,ToolPolicy.tool_id==p.tool_id))
    if row:
        for k,v in p.model_dump(exclude={"tool_id","workspace_id"}).items():setattr(row,k,v)
    else:row=ToolPolicy(organization_id=ctx.organization.id,**p.model_dump());db.add(row)
    audit(db,ctx.organization.id,"tool.policy.updated",actor_id=user.id,details={"tool":tool.key,"effect":p.effect,"approval":p.require_approval});return {"tool_id":tool.id,"effect":p.effect}

@router.get("/prompts")
async def prompts(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.read");rows=(await db.scalars(select(PromptDefinition).where(PromptDefinition.organization_id==ctx.organization.id).order_by(PromptDefinition.key,PromptDefinition.version.desc()))).all();return [{"id":x.id,"key":x.key,"version":x.version,"status":x.status,"input_variables":x.input_variables,"created_at":x.created_at} for x in rows]
@router.post("/prompts",status_code=201)
async def create_prompt(p:PromptCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.manage");version=int(await db.scalar(select(func.max(PromptDefinition.version)).where(PromptDefinition.organization_id==ctx.organization.id,PromptDefinition.key==p.key)) or 0)+1
    if p.status=="active":
        for old in (await db.scalars(select(PromptDefinition).where(PromptDefinition.organization_id==ctx.organization.id,PromptDefinition.key==p.key,PromptDefinition.status=="active"))).all():old.status="archived"
    row=PromptDefinition(organization_id=ctx.organization.id,version=version,created_by=user.id,**p.model_dump());db.add(row);await db.flush();return {"id":row.id,"version":version}

@router.get("/model-routes")
async def routes(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.read");rows=(await db.scalars(select(ModelRoute).where(ModelRoute.organization_id==ctx.organization.id))).all();return [{"id":x.id,"workspace_id":x.workspace_id,"task_type":x.task_type,"primary_model":x.primary_model,"fallback_models":x.fallback_models,"max_cost_cents":x.max_cost_cents,"max_tokens":x.max_tokens,"enabled":x.enabled} for x in rows]
@router.put("/model-routes")
async def route(p:RouteUpsert,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.manage");check_workspace(ctx,p.workspace_id);row=await db.scalar(select(ModelRoute).where(ModelRoute.organization_id==ctx.organization.id,ModelRoute.workspace_id==p.workspace_id,ModelRoute.task_type==p.task_type))
    if row:
        for k,v in p.model_dump(exclude={"workspace_id","task_type"}).items():setattr(row,k,v)
    else:row=ModelRoute(organization_id=ctx.organization.id,**p.model_dump());db.add(row)
    return {"task_type":p.task_type,"primary_model":p.primary_model}

@router.get("/workflows")
async def workflows(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.read");return [workflow_view(x) for x in (await db.scalars(select(Workflow).where(Workflow.organization_id==ctx.organization.id).order_by(Workflow.created_at.desc()))).all()]
@router.post("/workflows",status_code=201)
async def create_workflow(p:WorkflowCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.manage");check_workspace(ctx,p.workspace_id)
    try:graph=validate_graph(p.graph)
    except ValueError as exc:raise HTTPException(422,str(exc))
    row=Workflow(organization_id=ctx.organization.id,workspace_id=p.workspace_id,name=p.name,description=p.description,created_by=user.id);db.add(row);await db.flush();version=WorkflowVersion(organization_id=ctx.organization.id,workflow_id=row.id,version=1,graph=graph,change_note=p.change_note,created_by=user.id);db.add(version);await db.flush();row.active_version_id=version.id;audit(db,ctx.organization.id,"workflow.created",actor_id=user.id,details={"workflow_id":row.id});return {**workflow_view(row),"version":1}
@router.get("/workflows/{workflow_id}")
async def workflow_detail(workflow_id:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.read");row=await workflow_owned(db,ctx,workflow_id);versions=(await db.scalars(select(WorkflowVersion).where(WorkflowVersion.workflow_id==row.id).order_by(WorkflowVersion.version.desc()))).all();return {**workflow_view(row),"versions":[{"id":x.id,"version":x.version,"graph":x.graph,"change_note":x.change_note,"created_at":x.created_at} for x in versions]}
@router.post("/workflows/{workflow_id}/versions",status_code=201)
async def version(workflow_id:str,p:WorkflowVersionCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.manage");row=await workflow_owned(db,ctx,workflow_id)
    try:graph=validate_graph(p.graph)
    except ValueError as exc:raise HTTPException(422,str(exc))
    number=int(await db.scalar(select(func.max(WorkflowVersion.version)).where(WorkflowVersion.workflow_id==row.id)) or 0)+1;item=WorkflowVersion(organization_id=ctx.organization.id,workflow_id=row.id,version=number,graph=graph,change_note=p.change_note,created_by=user.id);db.add(item);await db.flush();return {"id":item.id,"version":number}
@router.post("/workflows/{workflow_id}/activate/{version_id}")
async def activate(workflow_id:str,version_id:str,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.manage");row=await workflow_owned(db,ctx,workflow_id);version=await db.get(WorkflowVersion,version_id)
    if not version or version.workflow_id!=row.id:raise HTTPException(404,"Version not found")
    evaluation=await db.scalar(select(EvaluationRun).where(EvaluationRun.organization_id==ctx.organization.id,EvaluationRun.workflow_version_id==version.id,EvaluationRun.passed.is_(True)).order_by(EvaluationRun.completed_at.desc()))
    if not evaluation:raise HTTPException(409,"A passing evaluation is required before activation")
    previous=row.active_version_id;row.active_version_id=version.id;row.status="active";audit(db,ctx.organization.id,"workflow.activated",actor_id=user.id,details={"from":previous,"to":version.id});return {"active_version_id":version.id,"rollback_version_id":previous}

@router.post("/workflows/{workflow_id}/runs",status_code=201)
async def start_run(workflow_id:str,p:RunCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.run");workflow=await workflow_owned(db,ctx,workflow_id)
    if workflow.status!="active" or not workflow.active_version_id:raise HTTPException(409,"Workflow is not active")
    existing=await db.scalar(select(WorkflowRun).where(WorkflowRun.organization_id==ctx.organization.id,WorkflowRun.idempotency_key==p.idempotency_key))
    if existing:return run_view(existing)
    row=WorkflowRun(organization_id=ctx.organization.id,workspace_id=workflow.workspace_id,workflow_id=workflow.id,version_id=workflow.active_version_id,user_id=user.id,input=p.input,budget_cents=p.budget_cents,idempotency_key=p.idempotency_key);db.add(row);await db.flush();audit(db,ctx.organization.id,"run.created",row.id,user.id,{"budget_cents":p.budget_cents});return run_view(row)
def run_view(x):return {"id":x.id,"workflow_id":x.workflow_id,"version_id":x.version_id,"status":x.status,"current_node_id":x.current_node_id,"input":x.input,"output":x.output,"budget_cents":x.budget_cents,"spent_cents":x.spent_cents,"parent_run_id":x.parent_run_id,"created_at":x.created_at,"completed_at":x.completed_at}
@router.get("/runs")
async def runs(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.read");return [run_view(x) for x in (await db.scalars(select(WorkflowRun).where(WorkflowRun.organization_id==ctx.organization.id).order_by(WorkflowRun.created_at.desc()).limit(100))).all()]
@router.get("/runs/{run_id}")
async def run_detail(run_id:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.read");row=await db.get(WorkflowRun,run_id)
    if not row or row.organization_id!=ctx.organization.id:raise HTTPException(404,"Run not found")
    steps=(await db.scalars(select(WorkflowStepRun).where(WorkflowStepRun.run_id==row.id).order_by(WorkflowStepRun.started_at))).all();approvals=(await db.scalars(select(WorkflowApproval).where(WorkflowApproval.run_id==row.id))).all();logs=(await db.scalars(select(OrchestrationAudit).where(OrchestrationAudit.run_id==row.id).order_by(OrchestrationAudit.created_at))).all()
    return {**run_view(row),"steps":[{"id":x.id,"node_id":x.node_id,"node_type":x.node_type,"attempt":x.attempt,"status":x.status,"input":x.input,"output":x.output,"error":x.error,"started_at":x.started_at,"completed_at":x.completed_at} for x in steps],"approvals":[{"id":x.id,"step_run_id":x.step_run_id,"risk_summary":x.risk_summary,"requested_action":x.requested_action,"status":x.status,"decision_note":x.decision_note} for x in approvals],"audit":[{"action":x.action,"details":x.details,"created_at":x.created_at} for x in logs]}
@router.post("/runs/{run_id}/advance")
async def advance(run_id:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.run");row=await db.get(WorkflowRun,run_id)
    if not row or row.organization_id!=ctx.organization.id:raise HTTPException(404,"Run not found")
    await execute_one(db,row,"api");return run_view(row)
@router.post("/runs/{run_id}/cancel")
async def cancel(run_id:str,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.run");row=await db.get(WorkflowRun,run_id)
    if not row or row.organization_id!=ctx.organization.id:raise HTTPException(404,"Run not found")
    if row.status in {"completed","failed","cancelled"}:raise HTTPException(409,"Run is already terminal")
    row.status="cancelled";row.completed_at=utc();audit(db,ctx.organization.id,"run.cancelled",row.id,user.id);return run_view(row)
@router.post("/runs/{run_id}/replay",status_code=201)
async def replay(run_id:str,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.run");old=await db.get(WorkflowRun,run_id)
    if not old or old.organization_id!=ctx.organization.id:raise HTTPException(404,"Run not found")
    row=WorkflowRun(organization_id=old.organization_id,workspace_id=old.workspace_id,workflow_id=old.workflow_id,version_id=old.version_id,user_id=user.id,input=old.input,budget_cents=old.budget_cents,idempotency_key=f"replay:{old.id}:{secrets.token_hex(6)}",parent_run_id=old.id);db.add(row);await db.flush();audit(db,ctx.organization.id,"run.replayed",row.id,user.id,{"source_run_id":old.id});return run_view(row)

@router.get("/approvals")
async def approvals(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.read");rows=(await db.scalars(select(WorkflowApproval).where(WorkflowApproval.organization_id==ctx.organization.id).order_by(WorkflowApproval.created_at.desc()).limit(100))).all();return [{"id":x.id,"run_id":x.run_id,"risk_summary":x.risk_summary,"requested_action":x.requested_action,"status":x.status,"requested_by":x.requested_by,"created_at":x.created_at} for x in rows]
@router.post("/approvals/{approval_id}/decision")
async def decide(approval_id:str,p:ApprovalDecision,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.approve");row=await db.get(WorkflowApproval,approval_id)
    if not row or row.organization_id!=ctx.organization.id:raise HTTPException(404,"Approval not found")
    if row.status!="pending":raise HTTPException(409,"Approval is already decided")
    if row.requested_by==user.id:raise HTTPException(409,"Requester cannot approve their own action")
    row.status=p.decision;row.decided_by=user.id;row.decision_note=p.note;row.decided_at=utc();run=await db.get(WorkflowRun,row.run_id);step=await db.get(WorkflowStepRun,row.step_run_id)
    if p.decision=="approved":run.status="queued";step.status="approved"
    else:run.status="rejected";run.completed_at=utc();step.status="rejected";step.completed_at=utc()
    audit(db,ctx.organization.id,"approval.decided",run.id,user.id,{"decision":p.decision,"approval_id":row.id});return {"id":row.id,"status":row.status}

@router.get("/memories")
async def memories(namespace:str|None=None,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.read");q=select(AgentMemory).where(AgentMemory.organization_id==ctx.organization.id,AgentMemory.user_id==user.id,AgentMemory.deleted_at.is_(None),or_(AgentMemory.expires_at.is_(None),AgentMemory.expires_at>utc()))
    if namespace:q=q.where(AgentMemory.namespace==namespace)
    rows=(await db.scalars(q.order_by(AgentMemory.created_at.desc()).limit(100))).all();return [{"id":x.id,"workspace_id":x.workspace_id,"namespace":x.namespace,"key":x.key,"value":x.value,"expires_at":x.expires_at,"run_id":x.run_id} for x in rows]
@router.put("/memories")
async def put_memory(p:MemoryPut,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.run");check_workspace(ctx,p.workspace_id);row=await db.scalar(select(AgentMemory).where(AgentMemory.organization_id==ctx.organization.id,AgentMemory.workspace_id==p.workspace_id,AgentMemory.user_id==user.id,AgentMemory.namespace==p.namespace,AgentMemory.key==p.key));expires=utc()+timedelta(seconds=p.ttl_seconds) if p.ttl_seconds else None
    if row:row.value=p.value;row.expires_at=expires;row.deleted_at=None;row.run_id=p.run_id
    else:row=AgentMemory(organization_id=ctx.organization.id,user_id=user.id,workspace_id=p.workspace_id,run_id=p.run_id,namespace=p.namespace,key=p.key,value=p.value,expires_at=expires);db.add(row)
    return {"namespace":p.namespace,"key":p.key,"expires_at":expires}
@router.delete("/memories/{memory_id}",status_code=204)
async def delete_memory(memory_id:str,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    row=await db.get(AgentMemory,memory_id)
    if not row or row.organization_id!=ctx.organization.id or row.user_id!=user.id:raise HTTPException(404,"Memory not found")
    row.deleted_at=utc();row.value={}

@router.get("/evaluations/datasets")
async def datasets(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.read");rows=(await db.scalars(select(EvaluationDataset).where(EvaluationDataset.organization_id==ctx.organization.id).order_by(EvaluationDataset.created_at.desc()))).all();return [{"id":x.id,"name":x.name,"version":x.version,"case_count":len(x.cases),"thresholds":x.thresholds} for x in rows]
@router.post("/evaluations/datasets",status_code=201)
async def create_dataset(p:DatasetCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.manage");row=EvaluationDataset(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump());db.add(row);await db.flush();return {"id":row.id,"case_count":len(row.cases)}
@router.post("/evaluations/datasets/{dataset_id}/run/{version_id}",status_code=201)
async def run_evaluation(dataset_id:str,version_id:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.manage");dataset=await db.get(EvaluationDataset,dataset_id);version=await db.get(WorkflowVersion,version_id)
    if not dataset or dataset.organization_id!=ctx.organization.id or not version or version.organization_id!=ctx.organization.id:raise HTTPException(404,"Dataset or version not found")
    row=await evaluate(db,dataset,version);return {"id":row.id,"score":row.score,"passed":row.passed,"results":row.results}

@router.get("/templates")
async def templates(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.read");rows=(await db.scalars(select(WorkflowTemplate).where(or_(WorkflowTemplate.organization_id==ctx.organization.id,WorkflowTemplate.organization_id.is_(None)),WorkflowTemplate.published.is_(True)).order_by(WorkflowTemplate.category,WorkflowTemplate.name))).all();return [{"id":x.id,"key":x.key,"name":x.name,"category":x.category,"version":x.version,"graph":x.graph,"organization_id":x.organization_id} for x in rows]
@router.post("/templates",status_code=201)
async def create_template(p:TemplateCreate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.manage")
    try:graph=validate_graph(p.graph)
    except ValueError as exc:raise HTTPException(422,str(exc))
    version=int(await db.scalar(select(func.max(WorkflowTemplate.version)).where(WorkflowTemplate.organization_id==ctx.organization.id,WorkflowTemplate.key==p.key)) or 0)+1;row=WorkflowTemplate(organization_id=ctx.organization.id,version=version,graph=graph,**p.model_dump(exclude={"graph"}));db.add(row);await db.flush();return {"id":row.id,"version":version}
@router.post("/templates/{template_id}/install",status_code=201)
async def install_template(template_id:str,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    require_permission(ctx,"agents.manage");template=await db.get(WorkflowTemplate,template_id)
    if not template or not template.published or template.organization_id not in {None,ctx.organization.id}:raise HTTPException(404,"Template not found")
    row=Workflow(organization_id=ctx.organization.id,workspace_id=ctx.workspace.id if ctx.workspace else None,name=template.name,description=f"Installed from {template.key}:v{template.version}",created_by=user.id);db.add(row);await db.flush();version=WorkflowVersion(organization_id=ctx.organization.id,workflow_id=row.id,version=1,graph=template.graph,change_note="Installed from marketplace",created_by=user.id);db.add(version);await db.flush();row.active_version_id=version.id;return {"id":row.id,"version_id":version.id}
