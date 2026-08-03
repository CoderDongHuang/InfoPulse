from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies import get_current_user,get_tenant_context
from app.models.planetary_resilience import *
from app.models.provable_autonomy import AgentCollectiveRun,DecisionProof,MemoryGovernanceRecord,PolicyModelCheck
from app.models.user import User
from app.schemas.planetary_resilience import *
from app.services.enterprise import TenantContext,require_permission
from app.services.planetary_resilience import *
from app.services.trusted_ecosystem import sign,view

router=APIRouter(prefix="/api/v1/planetary-resilience",tags=["Planetary intelligence resilience"])
@router.get("/overview")
async def overview(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"org.read");oid=ctx.organization.id
 async def count(m):return await db.scalar(select(func.count()).select_from(m).where(m.organization_id==oid))
 return {"proof_mesh":await count(ProofMeshEnvelope),"policy_registry":await count(PolicyProofRegistry),"pq_migrations":await count(PostQuantumMigration),"twin_runs":await count(PlanetaryTwinRun),"blocked_constitutions":await db.scalar(select(func.count()).select_from(AgentConstitutionRun).where(AgentConstitutionRun.organization_id==oid,AgentConstitutionRun.status=="blocked")),"resource_trades":await count(CrisisResourceTrade),"insurance_policies":await count(AutonomousInsurancePolicy),"memory_transfers":await count(VerifiableMemoryTransfer),"edge_messages":await count(EdgeMeshMessage),"public_audits":await count(PublicInterestAudit)}
@router.post("/proof-mesh",status_code=201)
async def proof_mesh(p:ProofMeshCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"audit.export");old=await db.scalar(select(ProofMeshEnvelope).where(ProofMeshEnvelope.organization_id==ctx.organization.id,ProofMeshEnvelope.idempotency_key==p.idempotency_key))
 if old:return view(old)
 proof=await db.scalar(select(DecisionProof).where(DecisionProof.id==p.decision_proof_id,DecisionProof.organization_id==ctx.organization.id));dependencies=(await db.scalars(select(ProofMeshEnvelope).where(ProofMeshEnvelope.id.in_(p.dependency_ids)))).all() if p.dependency_ids else [];gate=mesh_gate(bool(proof and proof.verified),p.trust_signatures,p.trust_threshold,[view(x) for x in dependencies]);payload=p.model_dump();row=ProofMeshEnvelope(organization_id=ctx.organization.id,created_by=user.id,mesh_hash=sign(payload,"proof-mesh"),status=gate["status"],**payload);db.add(row);await db.flush();return view(row)
@router.post("/proof-mesh/{mesh_id}/revoke")
async def revoke(mesh_id:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"audit.export");row=await db.scalar(select(ProofMeshEnvelope).where(ProofMeshEnvelope.id==mesh_id,ProofMeshEnvelope.organization_id==ctx.organization.id).with_for_update())
 if not row:raise HTTPException(404,"Proof mesh envelope not found")
 row.status="revoked";row.revoked_at=datetime.now(timezone.utc);dependents=(await db.scalars(select(ProofMeshEnvelope))).all()
 for item in dependents:
  if row.id in item.dependency_ids:item.status="blocked"
 await db.flush();return view(row)
@router.post("/policy-registry",status_code=201)
async def register_policy(p:PolicyRegistryCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"policy.manage");check=await db.scalar(select(PolicyModelCheck).where(PolicyModelCheck.id==p.model_check_id,PolicyModelCheck.organization_id==ctx.organization.id));
 if not check or check.status!="passed":raise HTTPException(409,"Passing model check required")
 payload=p.model_dump();row=PolicyProofRegistry(organization_id=ctx.organization.id,created_by=user.id,registry_signature=sign(payload,"policy-registry"),**payload);db.add(row);await db.flush();return view(row)
@router.post("/pq-migrations",status_code=201)
async def pq_migrate(p:PQMigrationCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"org.manage");subject={"type":p.subject_type,"id":p.subject_id,"classical":p.classical_fingerprint,"pq":p.pq_fingerprint};result=hybrid_sign(subject,p.classical_algorithm,p.pq_algorithm,p.historical_proofs);row=PostQuantumMigration(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(exclude={"historical_proofs"}),**result);db.add(row);await db.flush();return view(row)
@router.post("/planetary-twins",status_code=201)
async def twin(p:PlanetaryTwinCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"org.manage");result=planetary_cascade(p.domains,p.topology,p.shocks);row=PlanetaryTwinRun(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(),**result);db.add(row);await db.flush();return view(row)
@router.post("/constitutions",status_code=201)
async def constitution(p:ConstitutionCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"agents.manage");run=await db.scalar(select(AgentCollectiveRun).where(AgentCollectiveRun.id==p.collective_run_id,AgentCollectiveRun.organization_id==ctx.organization.id));
 if not run:raise HTTPException(404,"Agent collective run not found")
 result=constitution_gate(p.constitution,p.proposed_action,p.vote,p.human_veto);row=AgentConstitutionRun(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(),**result);db.add(row);await db.flush();return view(row)
@router.post("/resources",status_code=201)
async def resource(p:ResourceListingCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"billing.manage");row=CrisisResourceListing(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump());db.add(row);await db.flush();return view(row)
@router.post("/resource-trades",status_code=201)
async def trade(p:ResourceTradeCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"billing.manage");old=await db.scalar(select(CrisisResourceTrade).where(CrisisResourceTrade.buyer_organization_id==ctx.organization.id,CrisisResourceTrade.idempotency_key==p.idempotency_key));
 if old:return view(old)
 listing=await db.scalar(select(CrisisResourceListing).where(CrisisResourceListing.id==p.listing_id,CrisisResourceListing.status=="available").with_for_update())
 if not listing or listing.capacity<p.quantity or p.priority<listing.priority_floor:raise HTTPException(409,"Resource allocation unavailable")
 listing.capacity-=p.quantity;row=CrisisResourceTrade(organization_id=listing.organization_id,buyer_organization_id=ctx.organization.id,created_by=user.id,amount_cents=trade_amount(p.quantity,listing.unit_price_cents),**p.model_dump());db.add(row);await db.flush();return view(row)
@router.post("/resource-trades/{trade_id}/transition")
async def trade_transition(trade_id:str,p:TradeTransition,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"billing.manage");row=await db.scalar(select(CrisisResourceTrade).where(CrisisResourceTrade.id==trade_id,CrisisResourceTrade.buyer_organization_id==ctx.organization.id).with_for_update());
 if not row:raise HTTPException(404,"Crisis trade not found")
 listing=await db.get(CrisisResourceListing,row.listing_id);transition_trade(row,listing,p.action,p.receipt);await db.flush();return view(row)
@router.post("/insurance",status_code=201)
async def insurance(p:InsuranceCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"billing.manage");terms=insurance_terms(p.risk_signals,p.base_limit_cents);row=AutonomousInsurancePolicy(organization_id=ctx.organization.id,created_by=user.id,subject_type=p.subject_type,subject_id=p.subject_id,risk_signals={**p.risk_signals,"score":terms.pop("risk_score")},trigger=p.trigger,**terms);db.add(row);await db.flush();return view(row)
@router.post("/insurance/{policy_id}/claims")
async def claim(policy_id:str,p:InsuranceClaim,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"billing.manage");row=await db.scalar(select(AutonomousInsurancePolicy).where(AutonomousInsurancePolicy.id==policy_id,AutonomousInsurancePolicy.organization_id==ctx.organization.id).with_for_update());
 if not row:raise HTTPException(404,"Insurance policy not found")
 result=insurance_claim(row,p.event,p.loss_cents);row.claims=[*row.claims,result];row.reserve_cents=result["remaining_reserve_cents"];await db.flush();return result
@router.post("/memory-transfers",status_code=201)
async def memory_transfer(p:MemoryTransferCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"agents.manage");memory=await db.scalar(select(MemoryGovernanceRecord).where(MemoryGovernanceRecord.id==p.memory_record_id,MemoryGovernanceRecord.organization_id==ctx.organization.id).with_for_update())
 if not memory:raise HTTPException(404,"Memory record not found")
 result=memory_transfer_gate(memory,p.purpose,p.source_region,p.target_region,p.retention_until);row=VerifiableMemoryTransfer(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump(),**result);db.add(row)
 if result["status"]=="completed":memory.status="erased";memory.erasure_proof=result["source_erasure_proof"]
 await db.flush();return view(row)
@router.post("/edge-messages",status_code=201)
async def edge_message(p:EdgeMessageCreate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"org.manage");previous=await db.scalar(select(EdgeMeshMessage).where(EdgeMeshMessage.organization_id==ctx.organization.id,EdgeMeshMessage.node_id==p.node_id).order_by(EdgeMeshMessage.sequence.desc()));result=append_edge_message(previous,p.node_id,p.sequence,p.vector_clock,p.payload);row=EdgeMeshMessage(organization_id=ctx.organization.id,node_id=p.node_id,sequence=p.sequence,vector_clock=p.vector_clock,online=p.online,status="synced" if p.online else "queued",**result);db.add(row);await db.flush();return view(row)
@router.post("/edge-messages/converge")
async def edge_converge(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"org.manage");rows=(await db.scalars(select(EdgeMeshMessage).where(EdgeMeshMessage.organization_id==ctx.organization.id))).all();result=converge_edge(rows)
 for row in rows:row.status="synced";row.online=True
 await db.flush();return result
@router.post("/public-audits",status_code=201)
async def public_audit(p:PublicAuditCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"audit.export");result=public_commitment(p.metrics,p.fairness,p.externalities,p.resource_allocation,p.observer_signatures);row=PublicInterestAudit(organization_id=ctx.organization.id,created_by=user.id,scope=p.scope,metrics=p.metrics,fairness=p.fairness,externalities=p.externalities,resource_allocation=p.resource_allocation,**result);db.add(row);await db.flush();return view(row)
