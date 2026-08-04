from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies import get_current_user,get_tenant_context
from app.models.cognitive_infrastructure import *
from app.models.user import User
from app.schemas.cognitive_infrastructure import *
from app.services.cognitive_infrastructure import *
from app.services.enterprise import TenantContext,require_permission
from app.services.trusted_ecosystem import view
router=APIRouter(prefix="/api/v1/cognitive-infrastructure",tags=["Global cognitive infrastructure"])
@router.get("/overview")
async def overview(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"org.read");oid=ctx.organization.id
 async def count(m):return await db.scalar(select(func.count()).select_from(m).where(m.organization_id==oid))
 return {"certifications":await count(ProofCertification),"constitution_upgrades":await count(ConstitutionUpgrade),"archives":await count(QuantumTransparencyArchive),"signals":await count(PublicIntelligenceSignal),"epistemic_blocks":await db.scalar(select(func.count()).select_from(EpistemicAssessment).where(EpistemicAssessment.organization_id==oid,EpistemicAssessment.gate_status=="blocked")),"clearing_batches":await count(AutonomousClearingBatch),"allocations":await count(FairResourceAllocation),"scenarios":await count(LongHorizonScenario),"commitments":await count(IntergenerationalCommitment),"sovereign_builds":await count(SovereignStackBuild)}
@router.post("/certifications",status_code=201)
async def certification(p:CertificationCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"audit.export");result=certify_proofs(p.implementations,p.test_vectors,p.revocation_tests);row=ProofCertification(organization_id=ctx.organization.id,created_by=user.id,standard_version=p.standard_version,proof_type=p.proof_type,implementations=p.implementations,test_vectors=p.test_vectors,**result);db.add(row);await db.flush();return view(row)
@router.post("/constitution-upgrades",status_code=201)
async def constitution_upgrade(p:ConstitutionUpgradeCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"policy.manage");result=constitution_upgrade_gate(p.current_rules,p.proposed_rules,p.impact_simulation,p.vote,p.effective_at,p.rollback_plan);impact={**p.impact_simulation,"gate":result["gate"]};row=ConstitutionUpgrade(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(exclude={"impact_simulation"}),impact_simulation=impact,status=result["status"]);db.add(row);await db.flush();return view(row)
@router.post("/archives",status_code=201)
async def archive(p:ArchiveCreate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"audit.export");previous=await db.scalar(select(QuantumTransparencyArchive).where(QuantumTransparencyArchive.organization_id==ctx.organization.id).order_by(QuantumTransparencyArchive.sequence.desc()));sequence=previous.sequence+1 if previous else 1;result=append_archive(previous,p,sequence);row=QuantumTransparencyArchive(organization_id=ctx.organization.id,sequence=sequence,object_type=p.object_type,object_id=p.object_id,content_hash=p.content_hash,algorithm=p.algorithm,timestamp_witnesses=p.timestamp_witnesses,**result);db.add(row);await db.flush();return view(row)
@router.post("/public-signals",status_code=201)
async def signal(p:PublicSignalCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"benchmark.manage");result=signal_quality(p.sources,p.metric,p.allowed_purposes);row=PublicIntelligenceSignal(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(),**result);db.add(row);await db.flush();return view(row)
@router.post("/epistemic-assessments",status_code=201)
async def epistemic(p:EpistemicCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"policy.manage");result=epistemic_risk(p.evidence_graph,p.source_families,p.agent_outputs,p.narrative_signals);row=EpistemicAssessment(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(),**result);db.add(row);await db.flush();return view(row)
@router.post("/clearing",status_code=201)
async def clearing(p:ClearingCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"billing.manage");result=clear_assets(p.assets,p.obligations,p.prices,p.liquidity_buffer,p.stress_shock);row=AutonomousClearingBatch(organization_id=ctx.organization.id,created_by=user.id,network_key=p.network_key,assets=p.assets,obligations=p.obligations,prices=p.prices,liquidity_buffer=p.liquidity_buffer,**result);db.add(row);await db.flush();return view(row)
@router.post("/allocations",status_code=201)
async def allocation(p:AllocationCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"org.manage");result=fair_allocate(p.available_capacity,p.requests);row=FairResourceAllocation(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(),**result);db.add(row);await db.flush();return view(row)
@router.post("/scenarios",status_code=201)
async def scenario(p:ScenarioCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"org.manage");result=long_horizon(p.drivers,p.horizon_years,p.interventions);row=LongHorizonScenario(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(),**result);db.add(row);await db.flush();return view(row)
@router.post("/commitments",status_code=201)
async def commitment(p:CommitmentCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"audit.export");result=commitment_audit(p.baseline,p.current_state,p.cost_transfers,p.externalities,p.beneficiaries);row=IntergenerationalCommitment(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(),audit_result=result,status="on_track" if result["passed"] else "review");db.add(row);await db.flush();return view(row)
@router.post("/sovereign-builds",status_code=201)
async def sovereign_build(p:StackBuildCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"org.manage");status=build_gate(p.source_digest,p.artifact_digest,p.reproduction_digest,p.hardware_root,p.offline_capabilities);row=SovereignStackBuild(organization_id=ctx.organization.id,created_by=user.id,status=status,**p.model_dump());db.add(row);await db.flush();return view(row)
@router.post("/sovereign-upgrades",status_code=201)
async def sovereign_upgrade(p:StackUpgradeCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"org.manage");build=await db.scalar(select(SovereignStackBuild).where(SovereignStackBuild.id==p.build_id,SovereignStackBuild.organization_id==ctx.organization.id));
 if not build:raise HTTPException(404,"Sovereign build not found")
 status=upgrade_gate(build.status,p.signature_valid,p.offline_test,p.rollback_proof);row=SovereignStackUpgrade(organization_id=ctx.organization.id,created_by=user.id,status=status,**p.model_dump());db.add(row);await db.flush();return view(row)
