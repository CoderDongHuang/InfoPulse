from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user, get_tenant_context
from app.models.global_coordination import *
from app.models.user import User
from app.schemas.global_coordination import *
from app.services.enterprise import TenantContext, require_permission
from app.services.global_coordination import *
from app.services.trusted_ecosystem import digest, sign, view

router = APIRouter(prefix="/api/v1/global-coordination", tags=["Global intelligence coordination"])


@router.get("/overview")
async def overview(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.read")
    oid = ctx.organization.id
    async def count(model):
        return await db.scalar(select(func.count()).select_from(model).where(model.organization_id == oid))
    return {"nodes": await count(FederationNode), "proofs": await count(ProofVerification), "risks": await count(SystemicRiskSignal), "drifts": await db.scalar(select(func.count()).select_from(ControlObservation).where(ControlObservation.organization_id == oid, ControlObservation.status == "drifted")), "settlements": await count(GlobalSettlement), "crisis_rooms": await count(CrisisRoom)}


@router.post("/nodes", status_code=201)
async def create_node(p: NodeCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.manage")
    node = FederationNode(organization_id=ctx.organization.id, created_by=user.id, status="active", **p.model_dump())
    db.add(node); await db.flush(); return view(node)


@router.post("/negotiations", status_code=201)
async def negotiate(p: NegotiationCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.manage")
    old = await db.scalar(select(CapabilityNegotiation).where(CapabilityNegotiation.organization_id == ctx.organization.id, CapabilityNegotiation.idempotency_key == p.idempotency_key))
    if old: return view(old)
    local = await db.scalar(select(FederationNode).where(FederationNode.id == p.local_node_id, FederationNode.organization_id == ctx.organization.id))
    remote = await db.get(FederationNode, p.remote_node_id)
    if not local or not remote: raise HTTPException(404, "Federation node not found")
    result = negotiate_protocol(local, remote, p.presented_identity_fingerprint)
    row = CapabilityNegotiation(organization_id=ctx.organization.id, local_node_id=local.id, remote_node_id=remote.id, idempotency_key=p.idempotency_key, **result)
    db.add(row); await db.flush(); return view(row)


@router.post("/proofs", status_code=201)
async def proof(p: ProofCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "audit.export")
    result = verify_proof(p)
    row = ProofVerification(organization_id=ctx.organization.id, **p.model_dump(), status=result["status"])
    db.add(row); await db.flush(); return view(row)


@router.post("/contracts", status_code=201)
async def contract(p: ContractCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "policy.manage")
    result = evaluate_contract(p.proposal, p.constraints)
    row = ContractNegotiation(organization_id=ctx.organization.id, created_by=user.id, **p.model_dump(), counter_offer=result["counter_offer"], status=result["status"])
    db.add(row); await db.flush(); return {**view(row), "violations": result["violations"]}


@router.post("/regulatory/subscriptions", status_code=201)
async def subscription(p: SubscriptionCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "policy.manage"); row = RegulatorySubscription(organization_id=ctx.organization.id, created_by=user.id, **p.model_dump()); db.add(row); await db.flush(); return view(row)


@router.post("/regulatory/updates", status_code=201)
async def regulatory_update(p: RegulatoryUpdateCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "policy.manage")
    sub = await db.scalar(select(RegulatorySubscription).where(RegulatorySubscription.id == p.subscription_id, RegulatorySubscription.organization_id == ctx.organization.id).with_for_update())
    if not sub: raise HTTPException(404, "Regulatory subscription not found")
    result = apply_regulatory_delta(p.existing_rules, p.delta, p.emergency)
    row = RegulatoryUpdate(organization_id=ctx.organization.id, subscription_id=sub.id, version=p.version, delta=p.delta, conflicts=result["conflicts"], impact={"effective_rules": result["rules"]}, signature=sign(p.model_dump(), "regulatory-update"), emergency=p.emergency, status=result["status"])
    if result["status"] == "active": sub.active_version = p.version
    if p.emergency: sub.status = "suspended"
    db.add(row); await db.flush(); return view(row)


@router.post("/risks", status_code=201)
async def risk(p: RiskCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "policy.manage"); result = score_systemic_risk(p.factors, p.threshold); row = SystemicRiskSignal(organization_id=ctx.organization.id, risk_type=p.risk_type, subject_ids=p.subject_ids, threshold=p.threshold, score=result["score"], evidence={"factors": p.factors}, gate_status=result["gate_status"]); db.add(row); await db.flush(); return view(row)


@router.post("/controls/observe", status_code=201)
async def observe(p: ObservationCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "policy.manage"); result = detect_drift(p.observed_state, p.expected_state); row = ControlObservation(organization_id=ctx.organization.id, **p.model_dump(), **result); db.add(row); await db.flush(); return view(row)


@router.post("/arbitrations", status_code=201)
async def arbitration(p: ArbitrationCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "policy.manage"); row = ArbitrationCase(organization_id=ctx.organization.id, created_by=user.id, dispute_id=p.dispute_id, blind_evidence=blind_evidence(p.evidence), reproduction=p.reproduction, arbitrator_organization_id=p.arbitrator_organization_id, bond_cents=p.bond_cents); db.add(row); await db.flush(); return view(row)


@router.post("/arbitrations/{case_id}/decide")
async def decide(case_id: str, p: ArbitrationDecision, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "policy.manage"); row = await db.scalar(select(ArbitrationCase).where(ArbitrationCase.id == case_id, ArbitrationCase.organization_id == ctx.organization.id));
    if not row: raise HTTPException(404, "Arbitration case not found")
    row.decision = p.model_dump(exclude={"recovery_steps"}); row.reputation_recovery = {"steps": p.recovery_steps, "status": "scheduled" if p.recovery_steps else "not_required"}; row.status = "decided"; await db.flush(); return view(row)


@router.post("/evaluations", status_code=201)
async def evaluation(p: EvaluationCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "agents.manage"); result = aggregate_evaluation(p.participant_metrics, p.attestation); data = p.model_dump(exclude={"participant_metrics", "attestation"}); row = FederatedEvaluation(organization_id=ctx.organization.id, created_by=user.id, status="completed", **data, **result); db.add(row); await db.flush(); return view(row)


@router.post("/settlements", status_code=201)
async def settlement(p: SettlementCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "billing.manage"); result = reconcile_settlement(p.source_amount_cents, p.fx_rate, p.withholding_cents, p.escrow_cents, p.payout_cents); row = GlobalSettlement(organization_id=ctx.organization.id, locked_rate_hash=digest({"rate": p.fx_rate, "source": p.source_currency, "target": p.target_currency}), reconciliation=result, **p.model_dump()); db.add(row); await db.flush(); return view(row)


@router.post("/crisis-rooms", status_code=201)
async def crisis_room(p: CrisisRoomCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.manage"); participants = sorted(set(p.participants + [ctx.organization.id, p.commander_organization_id])); row = CrisisRoom(organization_id=ctx.organization.id, created_by=user.id, **p.model_dump(exclude={"participants"}), participants=participants); db.add(row); await db.flush(); return view(row)


@router.post("/crisis-rooms/{room_id}/commands", status_code=201)
async def crisis_command(room_id: str, p: CrisisCommandCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.manage"); room = await db.get(CrisisRoom, room_id)
    if not room: raise HTTPException(404, "Crisis room not found")
    return view(await append_crisis_command(db, ctx.organization.id, user.id, room, p))
