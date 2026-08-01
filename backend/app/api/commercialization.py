from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies import get_current_user,get_tenant_context
from app.models.action_loop import AnonymousBenchmark,ImpactMeasurement,ResponseAction
from app.models.commercialization import *
from app.models.platform import ConnectorInstallation
from app.models.user import User
from app.schemas.commercialization import *
from app.services.commercialization import checksum,consume_usage,execute_connector,serialize
from app.services.enterprise import TenantContext,require_permission
router=APIRouter(prefix="/api/v1/commercial",tags=["Commercial operations"])

@router.get("/overview")
async def overview(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"billing.read");oid=ctx.organization.id
 async def count(model):return await db.scalar(select(func.count()).select_from(model).where(model.organization_id==oid))
 usage=(await db.scalars(select(ProductUsage).where(ProductUsage.organization_id==oid).order_by(ProductUsage.updated_at.desc()))).all()
 return {"templates":await count(TemplatePackage),"approval_flows":await count(ApprovalFlow),"connectors":await count(ConnectorExecution),"actions":await count(ResponseAction),"usage":[serialize(x) for x in usage],"cost_cents":sum(x.cost_cents for x in usage)}

@router.get("/templates")
async def templates(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):require_permission(ctx,"action.read");return [serialize(x) for x in (await db.scalars(select(TemplatePackage).where(TemplatePackage.organization_id==ctx.organization.id))).all()]
@router.post("/templates",status_code=201)
async def create_template(p:TemplateCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"action.manage");x=TemplatePackage(organization_id=ctx.organization.id,key=p.key,name=p.name,description=p.description,visibility=p.visibility,current_version=1,created_by=user.id);db.add(x);await db.flush();v=TemplatePackageVersion(organization_id=ctx.organization.id,package_id=x.id,version=1,definition=p.definition,change_note=p.change_note,checksum=checksum(p.definition),created_by=user.id);db.add(v);await db.flush();return serialize(x)
@router.get("/templates/{pid}/versions")
async def versions(pid:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):require_permission(ctx,"action.read");return [serialize(x) for x in (await db.scalars(select(TemplatePackageVersion).where(TemplatePackageVersion.organization_id==ctx.organization.id,TemplatePackageVersion.package_id==pid).order_by(TemplatePackageVersion.version.desc()))).all()]
@router.post("/templates/{pid}/versions",status_code=201)
async def new_version(pid:str,p:TemplateVersionCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"action.manage");pkg=await db.scalar(select(TemplatePackage).where(TemplatePackage.id==pid,TemplatePackage.organization_id==ctx.organization.id).with_for_update())
 if not pkg:raise HTTPException(404,"Template not found")
 pkg.current_version+=1;v=TemplatePackageVersion(organization_id=ctx.organization.id,package_id=pid,version=pkg.current_version,definition=p.definition,change_note=p.change_note,checksum=checksum(p.definition),created_by=user.id);db.add(v);await db.flush();return serialize(v)
@router.post("/templates/{pid}/rollback/{version}",status_code=201)
async def rollback(pid:str,version:int,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"action.manage");target=await db.scalar(select(TemplatePackageVersion).where(TemplatePackageVersion.organization_id==ctx.organization.id,TemplatePackageVersion.package_id==pid,TemplatePackageVersion.version==version))
 if not target:raise HTTPException(404,"Template version not found")
 return await new_version(pid,TemplateVersionCreate(definition=target.definition,change_note=f"Rollback to v{version}"),ctx,user,db)

@router.get("/approval-flows")
async def flows(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):require_permission(ctx,"action.read");return [serialize(x) for x in (await db.scalars(select(ApprovalFlow).where(ApprovalFlow.organization_id==ctx.organization.id))).all()]
@router.post("/approval-flows",status_code=201)
async def create_flow(p:ApprovalFlowCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"action.manage");x=ApprovalFlow(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump());db.add(x);await db.flush();return serialize(x)
@router.post("/connectors/execute",status_code=202)
async def connector(p:ConnectorExecute,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):require_permission(ctx,"action.execute");return serialize(await execute_connector(db,ctx.organization.id,p))

@router.post("/metric-collectors",status_code=201)
async def collector(p:MetricCollectorCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"action.manage");x=MetricCollector(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump());db.add(x);await db.flush();return serialize(x)
@router.post("/attribution-audits",status_code=201)
async def attribution(p:AttributionAuditCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"action.manage");m=await db.scalar(select(ImpactMeasurement).where(ImpactMeasurement.id==p.measurement_id,ImpactMeasurement.organization_id==ctx.organization.id))
 if not m:raise HTTPException(404,"Measurement not found")
 x=AttributionAudit(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump());db.add(x);await db.flush();return serialize(x)
@router.get("/cost-report")
async def costs(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):require_permission(ctx,"billing.read");rows=(await db.scalars(select(ProductUsage).where(ProductUsage.organization_id==ctx.organization.id))).all();return {"currency":"CNY","total_cents":sum(x.cost_cents for x in rows),"allocations":[serialize(x) for x in rows]}
@router.post("/sla-policies",status_code=201)
async def sla(p:SLAPolicyCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"billing.manage");x=SLAPolicy(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump());db.add(x);await db.flush();return serialize(x)
@router.put("/entitlement")
async def entitlement(p:EntitlementUpdate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"billing.manage");x=await db.get(UsageEntitlement,ctx.organization.id) or UsageEntitlement(organization_id=ctx.organization.id);db.add(x)
 for k,v in p.model_dump().items():setattr(x,k,v)
 await db.flush();return serialize(x)
@router.post("/usage",status_code=201)
async def usage(p:UsageRecord,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):require_permission(ctx,"billing.manage");return serialize(await consume_usage(db,ctx.organization.id,**p.model_dump()))
@router.post("/benchmarks",status_code=201)
async def benchmark(p:BenchmarkPublish,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"benchmark.manage")
 if p.sample_size<p.k_anonymity:raise HTTPException(422,"Sample does not satisfy k-anonymity")
 x=AnonymousBenchmark(organization_id=ctx.organization.id,**p.model_dump());db.add(x);await db.flush();return serialize(x)
