from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user, get_tenant_context
from app.models.adaptive_intelligence import *
from app.models.user import User
from app.schemas.adaptive_intelligence import *
from app.services.adaptive_intelligence import *
from app.services.enterprise import TenantContext, require_permission
from app.services.trusted_ecosystem import sign, view

router = APIRouter(prefix="/api/v1/adaptive-os", tags=["Adaptive global intelligence OS"])


@router.get("/overview")
async def overview(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.read"); oid = ctx.organization.id
    async def count(model): return await db.scalar(select(func.count()).select_from(model).where(model.organization_id == oid))
    return {"rollouts": await count(ProtocolRollout), "policies": await count(PolicySynthesis), "transparency_entries": await count(TransparencyLog), "simulations": await count(TwinSimulation), "open_circuits": await db.scalar(select(func.count()).select_from(MarketRiskControl).where(MarketRiskControl.organization_id == oid, MarketRiskControl.circuit_state == "open")), "blocked_assurance": await db.scalar(select(func.count()).select_from(AssuranceSnapshot).where(AssuranceSnapshot.organization_id == oid, AssuranceSnapshot.gate_status == "blocked")), "proposals": await count(GovernanceProposal)}


@router.post("/protocol-rollouts", status_code=201)
async def rollout(p: RolloutCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.manage"); result = rollout_decision(p.compatibility_matrix, p.health); row = ProtocolRollout(organization_id=ctx.organization.id, created_by=user.id, **p.model_dump(), **result); db.add(row); await db.flush(); return view(row)


@router.post("/policy-syntheses", status_code=201)
async def synthesize(p: PolicySynthesisCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "policy.manage"); status = policy_gate(p.formal_result, p.sandbox_diff, p.approver_ids); row = PolicySynthesis(organization_id=ctx.organization.id, created_by=user.id, status=status, **p.model_dump()); db.add(row); await db.flush(); return view(row)


@router.post("/transparency", status_code=201)
async def transparency(p: TransparencyAppend, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "audit.export"); return view(await append_transparency(db, ctx.organization.id, p))


@router.get("/transparency/{entry_id}/verify")
async def verify_transparency(entry_id: str, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "audit.export"); row = await db.scalar(select(TransparencyLog).where(TransparencyLog.id == entry_id, TransparencyLog.organization_id == ctx.organization.id));
    if not row: raise HTTPException(404, "Transparency entry not found")
    return {"id": row.id, "verified": verify_inclusion(row), "merkle_root": row.merkle_root}


@router.post("/digital-twins", status_code=201)
async def twin(p: TwinRunCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.manage"); result = simulate_cascade(p.topology, p.shocks); row = TwinSimulation(organization_id=ctx.organization.id, created_by=user.id, **p.model_dump(), **result); db.add(row); await db.flush(); return view(row)


@router.post("/market-controls", status_code=201)
async def market(p: MarketControlCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "billing.manage"); result = market_gate(p.liquidity_limit_cents, p.collateral_haircut, p.anomaly_threshold, p.observed_anomaly, p.stress_loss_cents); data = p.model_dump(exclude={"observed_anomaly", "stress_loss_cents"}); row = MarketRiskControl(organization_id=ctx.organization.id, created_by=user.id, **data, **result); db.add(row); await db.flush(); return view(row)


@router.post("/sovereign-routes", status_code=201)
async def route(p: SovereignRouteCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "agents.manage"); result = select_sovereign_route(p.residency_region, p.constraints, p.candidates); row = SovereignRoute(organization_id=ctx.organization.id, created_by=user.id, **p.model_dump(), **result); db.add(row); await db.flush(); return view(row)


@router.post("/incidents", status_code=201)
async def incident(p: IncidentCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.manage"); result = orchestrate_incident(p.signal, p.playbooks); row = IncidentOrchestration(organization_id=ctx.organization.id, created_by=user.id, signal=p.signal, **result); db.add(row); await db.flush(); return view(row)


@router.post("/assurance", status_code=201)
async def assurance(p: AssuranceCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "policy.manage"); result = assurance_gate(p.evidence_age_hours, p.pass_rate, p.max_evidence_age_hours, p.minimum_confidence); row = AssuranceSnapshot(organization_id=ctx.organization.id, control_id=p.control_id, evidence_age_hours=p.evidence_age_hours, pass_rate=p.pass_rate, **result); db.add(row); await db.flush(); return view(row)


@router.post("/sustainability", status_code=201)
async def sustainability(p: SustainabilityCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "billing.manage"); result = sustainability_accounting(p.compute_wh, p.storage_gb_hours, p.transfer_gb, p.carbon_factor, p.water_factor); data = p.model_dump(exclude={"compute_wh", "storage_gb_hours", "transfer_gb", "carbon_factor", "water_factor"}); row = SustainabilityLedger(organization_id=ctx.organization.id, **data, **result); db.add(row); await db.flush(); return view(row)


@router.post("/governance/proposals", status_code=201)
async def proposal(p: ProposalCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.manage"); row = GovernanceProposal(organization_id=ctx.organization.id, created_by=user.id, **p.model_dump()); db.add(row); await db.flush(); return view(row)


@router.post("/governance/proposals/{proposal_id}/votes", status_code=201)
async def vote(proposal_id: str, p: VoteCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.manage"); proposal = await db.get(GovernanceProposal, proposal_id)
    if not proposal or proposal.status != "voting": raise HTTPException(404, "Open governance proposal not found")
    row = GovernanceVote(organization_id=proposal.organization_id, proposal_id=proposal.id, voter_organization_id=ctx.organization.id, signature=sign({"proposal": proposal.id, **p.model_dump()}, "governance-vote"), **p.model_dump()); db.add(row); await db.flush(); return view(row)


@router.post("/governance/proposals/{proposal_id}/finalize")
async def finalize(proposal_id: str, p: ProposalFinalize, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.manage"); proposal = await db.scalar(select(GovernanceProposal).where(GovernanceProposal.id == proposal_id, GovernanceProposal.organization_id == ctx.organization.id).with_for_update())
    if not proposal: raise HTTPException(404, "Governance proposal not found")
    votes = (await db.scalars(select(GovernanceVote).where(GovernanceVote.proposal_id == proposal.id))).all(); proposal.result = governance_result(votes, p.eligible_weight, proposal.quorum_weight, proposal.veto_conditions); proposal.status = "passed" if proposal.result["passed"] else "rejected"; await db.flush(); return view(proposal)
