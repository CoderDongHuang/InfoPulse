from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies import get_current_user,get_tenant_context
from app.models.cognitive_commons import *
from app.models.cognitive_infrastructure import FairResourceAllocation,QuantumTransparencyArchive,SovereignStackBuild
from app.models.user import User
from app.schemas.cognitive_commons import *
from app.services.cognitive_commons import *
from app.services.enterprise import TenantContext,require_permission
from app.services.trusted_ecosystem import view
router=APIRouter(prefix="/api/v1/cognitive-commons",tags=["Global cognitive commons"])
@router.get("/overview")
async def overview(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"org.read");oid=ctx.organization.id
 async def n(m):return await db.scalar(select(func.count()).select_from(m).where(m.organization_id==oid))
 return {"consensus":await n(ProofConsensusRound),"constitutions":await n(FederatedConstitutionProtocol),"preservations":await n(EvidencePreservation),"causal_signals":await n(CausalSignalValidation),"dissent_markets":await n(DissentMarket),"treasuries":await n(PublicTreasury),"appeals":await n(AllocationAppeal),"century_scenarios":await n(CenturyRiskScenario),"safety_valves":await n(CivilizationSafetyValve),"releases":await n(SovereignFederatedRelease)}
@router.post("/consensus",status_code=201)
async def consensus(p:ConsensusCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"audit.export");r=bft_consensus(p.nodes,p.votes,p.fault_tolerance);x=ProofConsensusRound(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(),**r);db.add(x);await db.flush();return view(x)
@router.post("/constitutions",status_code=201)
async def constitution(p:ConstitutionProtocolCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"policy.manage");r=constitution_compatibility(p.constitutions,p.required_permission,p.amendment);x=FederatedConstitutionProtocol(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(),**r);db.add(x);await db.flush();return view(x)
@router.post("/evidence-preservations",status_code=201)
async def preserve(p:EvidencePreserveCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"audit.export");archive=await db.scalar(select(QuantumTransparencyArchive).where(QuantumTransparencyArchive.id==p.archive_id,QuantumTransparencyArchive.organization_id==ctx.organization.id));
 if not archive:raise HTTPException(404,"Archive not found")
 r=preserve_evidence(p.previous_proof,p.retired_algorithm,p.new_algorithm,p.timestamp_witnesses);x=EvidencePreservation(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(),**r);db.add(x);await db.flush();return view(x)
@router.post("/causal-validations",status_code=201)
async def causal(p:CausalValidationCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"benchmark.manage");r=causal_validate(p.experiments,p.counterfactuals);x=CausalSignalValidation(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(),**r);db.add(x);await db.flush();return view(x)
@router.post("/dissent-markets",status_code=201)
async def dissent(p:DissentMarketCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"billing.manage");r=settle_dissent(p.positions,p.reward_pool_cents);x=DissentMarket(organization_id=ctx.organization.id,created_by=user.id,claim_id=p.claim_id,positions=p.positions,**r);db.add(x);await db.flush();return view(x)
@router.post("/treasuries",status_code=201)
async def treasury(p:TreasuryCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"billing.manage");r=reconcile_treasury(p.opening_cents,p.revenues,p.grants,p.expenses,p.reserve_cents);x=PublicTreasury(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(),**r);db.add(x);await db.flush();return view(x)
@router.post("/appeals",status_code=201)
async def appeal(p:AppealCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"org.manage");allocation=await db.scalar(select(FairResourceAllocation).where(FairResourceAllocation.id==p.allocation_id,FairResourceAllocation.organization_id==ctx.organization.id));
 if not allocation:raise HTTPException(404,"Allocation not found")
 r=appeal_allocation(allocation,p.evidence,p.appellant_key,p.claimed_amount,p.compensation_rate_cents);x=AllocationAppeal(organization_id=ctx.organization.id,created_by=user.id,allocation_id=p.allocation_id,appellant_key=p.appellant_key,**r);db.add(x);await db.flush();return view(x)
@router.post("/century-scenarios",status_code=201)
async def century(p:CenturyScenarioCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"org.manage");r=century_scenario(p.domains,p.horizon_years,p.interactions,p.interventions);x=CenturyRiskScenario(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(),**r);db.add(x);await db.flush();return view(x)
@router.post("/safety-valves",status_code=201)
async def safety(p:SafetyValveCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"org.manage");r=safety_valve_state(p.pause_signatures,p.pause_threshold,p.degraded_capabilities,p.recovery_approvals,p.drill_evidence);x=CivilizationSafetyValve(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(),state=r["state"],drill_evidence={**p.drill_evidence,"gate":r["gate"]});db.add(x);await db.flush();return view(x)
@router.post("/federated-releases",status_code=201)
async def release(p:FederatedReleaseCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"org.manage");build=await db.scalar(select(SovereignStackBuild).where(SovereignStackBuild.id==p.build_id,SovereignStackBuild.organization_id==ctx.organization.id));
 if not build:raise HTTPException(404,"Sovereign build not found")
 r=federated_release_gate(build,p.mirrors,p.offline_patch,p.node_attestations,p.compatibility);x=SovereignFederatedRelease(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(),**r);db.add(x);await db.flush();return view(x)
