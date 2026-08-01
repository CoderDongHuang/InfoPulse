from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies import get_current_user,get_tenant_context
from app.models.autonomous_enterprise import *
from app.models.user import User
from app.schemas.autonomous_enterprise import *
from app.services.autonomous_enterprise import *
from app.services.enterprise import TenantContext,require_permission
router=APIRouter(prefix="/api/v1/autonomy",tags=["Autonomous enterprise"])
@router.get("/overview")
async def overview(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"org.read");oid=ctx.organization.id
 async def n(m):return await db.scalar(select(func.count()).select_from(m).where(m.organization_id==oid))
 return {"approval_runs":await n(ApprovalRun),"experiments":await n(CausalExperiment),"policies":await n(PolicyBundle),"controls":await n(ComplianceControl),"drills":await n(RecoveryDrill),"safety_evaluations":await n(SafetyEvaluation)}
@router.post("/credentials",status_code=201)
async def credential(p:CredentialLeaseCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"integrations.approve");x=ConnectorCredentialLease(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump());db.add(x);await db.flush();return view(x)
@router.post("/credentials/{cid}/revoke")
async def revoke(cid:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"integrations.approve")
 x=await db.scalar(select(ConnectorCredentialLease).where(ConnectorCredentialLease.id==cid,ConnectorCredentialLease.organization_id==ctx.organization.id))
 if not x:raise HTTPException(404,"Credential lease not found")
 x.status="revoked";x.secret_reference="";await db.flush();return view(x)
@router.post("/credentials/{cid}/rotate",status_code=201)
async def rotate(cid:str,p:CredentialLeaseCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"integrations.approve");old=await db.scalar(select(ConnectorCredentialLease).where(ConnectorCredentialLease.id==cid,ConnectorCredentialLease.organization_id==ctx.organization.id,ConnectorCredentialLease.status=="active"))
 if not old:raise HTTPException(404,"Active credential lease not found")
 if old.installation_id!=p.installation_id or old.provider!=p.provider:raise HTTPException(422,"Rotation target mismatch")
 old.status="rotated";old.secret_reference="";x=ConnectorCredentialLease(organization_id=ctx.organization.id,created_by=user.id,rotated_from_id=old.id,**p.model_dump());db.add(x);await db.flush();return view(x)
@router.post("/credentials/{cid}/health")
async def health(cid:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"integrations.approve");x=await db.scalar(select(ConnectorCredentialLease).where(ConnectorCredentialLease.id==cid,ConnectorCredentialLease.organization_id==ctx.organization.id))
 if not x:raise HTTPException(404,"Credential lease not found")
 x.last_health_at=datetime.now(timezone.utc);return {"id":x.id,"healthy":x.status=="active" and (x.expires_at is None or x.expires_at>x.last_health_at),"region":x.region,"egress_policy":x.egress_policy}
@router.post("/approval-runs",status_code=201)
async def approval(p:ApprovalRunCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"action.write");return view(await start_approval(db,ctx.organization.id,user.id,p))
@router.post("/approval-runs/{rid}/decide")
async def decision(rid:str,p:ApprovalDecision,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"action.approve");return view(await decide_node(db,ctx.organization.id,user.id,rid,p))
@router.post("/experiments",status_code=201)
async def experiment(p:CausalExperimentCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"action.manage");effect=causal_effect(p.treatment,p.control);x=CausalExperiment(organization_id=ctx.organization.id,created_by=user.id,effect=effect,status="ready" if p.power>=.8 else "underpowered",**p.model_dump());db.add(x);await db.flush();return view(x)
@router.post("/ledger",status_code=201)
async def ledger(p:LedgerCreate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):require_permission(ctx,"billing.manage");x=FinancialLedger(organization_id=ctx.organization.id,**p.model_dump());db.add(x);await db.flush();return view(x)
@router.post("/billing-documents",status_code=201)
async def bill(p:BillingDocumentCreate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):require_permission(ctx,"billing.manage");data=p.model_dump();x=BillingDocument(organization_id=ctx.organization.id,checksum=digest(data),**data);db.add(x);await db.flush();return view(x)
@router.post("/payments/reconcile")
async def reconcile(p:PaymentReconcile,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"billing.manage");entry=await db.scalar(select(FinancialLedger).where(FinancialLedger.organization_id==ctx.organization.id,FinancialLedger.external_reference==p.external_reference))
 if not entry:raise HTTPException(404,"Ledger entry not found")
 matched=entry.amount_cents==p.amount_cents and entry.currency==p.currency;entry.status="reconciled" if matched else "mismatch";entry.provider=p.provider;entry.metadata_json={**entry.metadata_json,"provider_reference":p.provider_reference};await db.flush();return {"matched":matched,"entry":view(entry)}
@router.get("/finops/forecast")
async def finops(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"billing.read");rows=(await db.scalars(select(FinancialLedger).where(FinancialLedger.organization_id==ctx.organization.id).order_by(FinancialLedger.created_at))).all();by_department={}
 for row in rows:by_department[row.department]=by_department.get(row.department,0)+row.amount_cents
 return {**forecast_cost([x.amount_cents for x in rows]),"chargeback":by_department,"unit_economics":{"entries":len(rows),"cost_per_entry_cents":round(sum(x.amount_cents for x in rows)/len(rows)) if rows else 0}}
@router.post("/privacy-budgets",status_code=201)
async def budget(p:PrivacyBudgetCreate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):require_permission(ctx,"benchmark.manage");x=PrivacyBudget(organization_id=ctx.organization.id,**p.model_dump());db.add(x);await db.flush();return view(x)
@router.post("/privacy-queries",status_code=201)
async def query(p:PrivacyQuery,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"benchmark.read");return view(await spend_privacy(db,ctx.organization.id,user.id,p))
@router.post("/policies",status_code=201)
async def policy(p:PolicyCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"policy.manage");b=PolicyBundle(organization_id=ctx.organization.id,key=p.key,name=p.name,current_version=1,created_by=user.id);db.add(b);await db.flush();sim=simulate_policy(p.rules,p.test_cases);v=PolicyVersion(organization_id=ctx.organization.id,bundle_id=b.id,version=1,rules=p.rules,test_cases=p.test_cases,simulation=sim,checksum=digest(p.rules),status="validated" if sim["ready"] else "draft",created_by=user.id);db.add(v);await db.flush();return {"bundle":view(b),"version":view(v)}
@router.post("/policies/{bid}/publish")
async def publish(bid:str,p:PolicyPublish,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"policy.manage");b=await db.scalar(select(PolicyBundle).where(PolicyBundle.id==bid,PolicyBundle.organization_id==ctx.organization.id));v=await db.scalar(select(PolicyVersion).where(PolicyVersion.bundle_id==bid,PolicyVersion.version==p.version,PolicyVersion.organization_id==ctx.organization.id))
 if not b or not v:raise HTTPException(404,"Policy version not found")
 if not v.simulation.get("ready"):raise HTTPException(409,"Policy simulation has not passed")
 b.active_version=v.version;b.canary_percent=p.canary_percent;v.status="active";await db.flush();return view(b)
@router.post("/recovery-drills",status_code=201)
async def drill(p:RecoveryDrillCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"org.manage");ok=p.actual_rpo_minutes is not None and p.actual_rto_minutes is not None and p.actual_rpo_minutes<=p.rpo_target_minutes and p.actual_rto_minutes<=p.rto_target_minutes and p.isolation_verified;x=RecoveryDrill(organization_id=ctx.organization.id,created_by=user.id,status="passed" if ok else "failed",**p.model_dump());db.add(x);await db.flush();return view(x)
@router.post("/compliance/controls",status_code=201)
async def control(p:ComplianceControlCreate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):require_permission(ctx,"audit.export");x=ComplianceControl(organization_id=ctx.organization.id,**p.model_dump());db.add(x);await db.flush();return view(x)
@router.post("/compliance/evidence",status_code=201)
async def evidence(p:ComplianceEvidenceCreate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"audit.export")
 c=await db.scalar(select(ComplianceControl).where(ComplianceControl.id==p.control_id,ComplianceControl.organization_id==ctx.organization.id))
 if not c:raise HTTPException(404,"Control not found")
 x=ComplianceEvidence(organization_id=ctx.organization.id,**p.model_dump());db.add(x);await db.flush();return view(x)
@router.get("/compliance/audit-pack")
async def audit_pack(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"audit.export");controls=(await db.scalars(select(ComplianceControl).where(ComplianceControl.organization_id==ctx.organization.id))).all();evidence=(await db.scalars(select(ComplianceEvidence).where(ComplianceEvidence.organization_id==ctx.organization.id))).all();payload={"organization_id":ctx.organization.id,"generated_at":datetime.now(timezone.utc).isoformat(),"controls":[view(x) for x in controls],"evidence":[view(x) for x in evidence]};return {**payload,"checksum":digest(payload)}
@router.post("/safety-evaluations",status_code=201)
async def safety(p:SafetyEvaluationCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"policy.manage");passed=p.score>=80 and not p.permission_drift and p.rollback_verified;x=SafetyEvaluation(organization_id=ctx.organization.id,created_by=user.id,gate_status="passed" if passed else "blocked",**p.model_dump());db.add(x);await db.flush();return view(x)
