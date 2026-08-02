from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user, get_tenant_context
from app.models.provable_autonomy import *
from app.models.user import User
from app.schemas.provable_autonomy import *
from app.services.enterprise import TenantContext, require_permission
from app.services.provable_autonomy import *
from app.services.trusted_ecosystem import digest, view

router = APIRouter(prefix="/api/v1/provable-autonomy", tags=["Provable autonomy and global continuity"])


@router.get("/overview")
async def overview(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.read"); oid = ctx.organization.id
    async def count(model): return await db.scalar(select(func.count()).select_from(model).where(model.organization_id == oid))
    return {"proofs": await count(DecisionProof), "model_checks": await count(PolicyModelCheck), "replicas": await count(RegionReplica), "quarantined_memories": await db.scalar(select(func.count()).select_from(MemoryGovernanceRecord).where(MemoryGovernanceRecord.organization_id == oid, MemoryGovernanceRecord.status == "quarantined")), "blocked_collectives": await db.scalar(select(func.count()).select_from(AgentCollectiveRun).where(AgentCollectiveRun.organization_id == oid, AgentCollectiveRun.status == "blocked")), "markets": await count(PredictionMarket), "kernel_tests": await count(DisasterKernelSnapshot), "settlements": await count(LiabilitySettlement)}


@router.post("/decision-proofs", status_code=201)
async def decision_proof(p: DecisionProofCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "agents.manage"); result = compile_decision_proof(p); row = DecisionProof(organization_id=ctx.organization.id, created_by=user.id, action_id=p.action_id, objective=p.objective, constraints=p.constraints, **result); db.add(row); await db.flush(); return view(row)


@router.get("/decision-proofs/{proof_id}/verify")
async def verify_proof(proof_id: str, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "audit.export"); row = await db.scalar(select(DecisionProof).where(DecisionProof.id == proof_id, DecisionProof.organization_id == ctx.organization.id));
    if not row: raise HTTPException(404, "Decision proof not found")
    return {"id": row.id, "verified": row.verified and verify_decision_proof(row.proof), "status": row.status}


@router.post("/model-checks", status_code=201)
async def check_policy(p: ModelCheckCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "policy.manage"); result = model_check(p.states, p.transitions, p.properties); row = PolicyModelCheck(organization_id=ctx.organization.id, created_by=user.id, **p.model_dump(), **result); db.add(row); await db.flush(); return view(row)


@router.post("/replicas", status_code=201)
async def replica(p: ReplicaCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.manage"); row = RegionReplica(organization_id=ctx.organization.id, recovery_point=digest({"state": p.state, "clock": p.vector_clock}), **p.model_dump()); db.add(row); await db.flush(); return view(row)


@router.post("/replicas/merge")
async def merge(p: ReplicaMerge, ctx: TenantContext = Depends(get_tenant_context)):
    require_permission(ctx, "org.manage"); return merge_replicas(p.replicas)


@router.post("/regulatory-partitions", status_code=201)
async def partition(p: RegulatoryPartitionCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "policy.manage"); result = partition_regulation(p.region, p.rules, p.requested_capabilities, p.data_paths); row = RegulatoryPartition(organization_id=ctx.organization.id, created_by=user.id, product_key=p.product_key, region=p.region, rules=p.rules, **result); db.add(row); await db.flush(); return view(row)


@router.post("/memories", status_code=201)
async def memory(p: MemoryCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "agents.manage"); result = memory_gate(p.expires_at, p.contamination_score); row = MemoryGovernanceRecord(organization_id=ctx.organization.id, created_by=user.id, **p.model_dump(), **result); db.add(row); await db.flush(); return view(row)


@router.post("/memories/{memory_id}/erase")
async def erase(memory_id: str, p: MemoryErase, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "agents.manage"); row = await db.scalar(select(MemoryGovernanceRecord).where(MemoryGovernanceRecord.id == memory_id, MemoryGovernanceRecord.organization_id == ctx.organization.id).with_for_update());
    if not row: raise HTTPException(404, "Memory governance record not found")
    row.erasure_proof = erase_memory(row.memory_key, row.content_hash, p.reason); row.status = "erased"; await db.flush(); return view(row)


@router.post("/collectives", status_code=201)
async def collective(p: CollectiveCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "agents.manage"); result = collective_gate(p.agent_ids, p.delegation_graph, p.tool_grants, p.budget_cents, p.spent_cents, p.communication_edges, p.limits); data = p.model_dump(exclude={"limits"}); row = AgentCollectiveRun(organization_id=ctx.organization.id, created_by=user.id, **data, **result); db.add(row); await db.flush(); return view(row)


@router.post("/prediction-markets", status_code=201)
async def market(p: MarketCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "billing.manage"); row = PredictionMarket(organization_id=ctx.organization.id, created_by=user.id, **p.model_dump()); db.add(row); await db.flush(); return view(row)


@router.post("/prediction-markets/{market_id}/forecasts", status_code=201)
async def forecast(market_id: str, p: ForecastCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "billing.manage"); market = await db.get(PredictionMarket, market_id)
    if not market or market.status != "open": raise HTTPException(404, "Open prediction market not found")
    row = ForecastPosition(organization_id=market.organization_id, market_id=market.id, forecaster_organization_id=ctx.organization.id, **p.model_dump()); db.add(row); await db.flush(); positions = (await db.scalars(select(ForecastPosition).where(ForecastPosition.market_id == market.id))).all(); aggregate = aggregate_forecasts(positions); market.aggregate_probability = aggregate["aggregate_probability"]; market.manipulation_score = aggregate["manipulation_score"]; await db.flush(); return {**view(row), "market_gate": aggregate["gate_status"]}


@router.post("/prediction-markets/{market_id}/settle")
async def settle_market(market_id: str, p: MarketSettle, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "billing.manage"); market = await db.scalar(select(PredictionMarket).where(PredictionMarket.id == market_id, PredictionMarket.organization_id == ctx.organization.id).with_for_update())
    if not market: raise HTTPException(404, "Prediction market not found")
    positions = (await db.scalars(select(ForecastPosition).where(ForecastPosition.market_id == market.id))).all(); result = settle_forecasts(positions, p.outcome, market.liquidity_cents)
    for position, score, payout in zip(positions, result["scores"], result["payouts"]): position.score = score; position.payout_cents = payout
    market.outcome = p.outcome; market.settlement = result; market.status = "settled"; await db.flush(); return view(market)


@router.post("/disaster-kernel/tests", status_code=201)
async def disaster(p: DisasterTestCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.manage"); result = disaster_kernel_gate(p.unavailable_dependencies, p.available_capabilities, p.offline_identity, p.manual_takeover); row = DisasterKernelSnapshot(organization_id=ctx.organization.id, created_by=user.id, **p.model_dump(), **result); db.add(row); await db.flush(); return view(row)


@router.post("/green-schedules", status_code=201)
async def schedule(p: GreenScheduleCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "agents.manage"); result = green_schedule(p.residency_region, p.constraints, p.candidates); row = GreenSchedule(organization_id=ctx.organization.id, created_by=user.id, **p.model_dump(), **result); db.add(row); await db.flush(); return view(row)


@router.post("/liability-settlements", status_code=201)
async def liability(p: LiabilityCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "billing.manage"); result = liability_accounting(p.loss_cents, p.compensation_cents, p.recovery_cents, p.reserve_cents, p.responsible_parties); data = p.model_dump(exclude={"responsible_parties"}); row = LiabilitySettlement(organization_id=ctx.organization.id, created_by=user.id, **data, **result); db.add(row); await db.flush(); return view(row)
