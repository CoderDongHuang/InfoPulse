"""Stage 24 adaptive global intelligence operating system models."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


class ProtocolRollout(Base):
    __tablename__ = "protocol_rollouts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    protocol_key: Mapped[str] = mapped_column(String(100))
    from_version: Mapped[str] = mapped_column(String(30))
    to_version: Mapped[str] = mapped_column(String(30))
    compatibility_matrix: Mapped[dict] = mapped_column(JSON, default=dict)
    canary_percent: Mapped[int] = mapped_column(Integer, default=5)
    health: Mapped[dict] = mapped_column(JSON, default=dict)
    rollback_reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="draft")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PolicySynthesis(Base):
    __tablename__ = "policy_syntheses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    regulatory_update_id: Mapped[str | None] = mapped_column(ForeignKey("regulatory_updates.id", ondelete="SET NULL"))
    candidate_policy: Mapped[dict] = mapped_column(JSON, default=dict)
    formal_result: Mapped[dict] = mapped_column(JSON, default=dict)
    sandbox_diff: Mapped[dict] = mapped_column(JSON, default=dict)
    approver_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(24), default="candidate")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TransparencyLog(Base):
    __tablename__ = "transparency_logs"
    __table_args__ = (UniqueConstraint("organization_id", "sequence", name="uq_transparency_sequence"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    object_type: Mapped[str] = mapped_column(String(40))
    object_id: Mapped[str] = mapped_column(String(80))
    leaf_hash: Mapped[str] = mapped_column(String(64))
    previous_root: Mapped[str] = mapped_column(String(64), default="")
    merkle_root: Mapped[str] = mapped_column(String(64))
    witness_signatures: Mapped[list] = mapped_column(JSON, default=list)
    inclusion_proof: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TwinSimulation(Base):
    __tablename__ = "twin_simulations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    scenario_type: Mapped[str] = mapped_column(String(50))
    topology: Mapped[dict] = mapped_column(JSON, default=dict)
    shocks: Mapped[list] = mapped_column(JSON, default=list)
    cascade_path: Mapped[list] = mapped_column(JSON, default=list)
    recovery_plan: Mapped[list] = mapped_column(JSON, default=list)
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    replay_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="completed")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class MarketRiskControl(Base):
    __tablename__ = "market_risk_controls"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    market_key: Mapped[str] = mapped_column(String(100))
    liquidity_limit_cents: Mapped[int] = mapped_column(Integer)
    collateral_haircut: Mapped[float] = mapped_column(Float)
    anomaly_threshold: Mapped[float] = mapped_column(Float)
    stress_result: Mapped[dict] = mapped_column(JSON, default=dict)
    circuit_state: Mapped[str] = mapped_column(String(20), default="closed")
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class SovereignRoute(Base):
    __tablename__ = "sovereign_routes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    request_key: Mapped[str] = mapped_column(String(120))
    residency_region: Mapped[str] = mapped_column(String(40))
    selected_region: Mapped[str] = mapped_column(String(40), default="")
    selected_model: Mapped[str] = mapped_column(String(100), default="")
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)
    candidates: Mapped[list] = mapped_column(JSON, default=list)
    decision: Mapped[dict] = mapped_column(JSON, default=dict)
    cross_border: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="blocked")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class IncidentOrchestration(Base):
    __tablename__ = "incident_orchestrations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    signal: Mapped[dict] = mapped_column(JSON, default=dict)
    severity: Mapped[str] = mapped_column(String(20))
    playbook: Mapped[list] = mapped_column(JSON, default=list)
    escalation: Mapped[dict] = mapped_column(JSON, default=dict)
    timeline: Mapped[list] = mapped_column(JSON, default=list)
    review: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="active")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class AssuranceSnapshot(Base):
    __tablename__ = "assurance_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    control_id: Mapped[str] = mapped_column(ForeignKey("compliance_controls.id", ondelete="CASCADE"))
    evidence_age_hours: Mapped[int] = mapped_column(Integer)
    pass_rate: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    sampling_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    gate_status: Mapped[str] = mapped_column(String(20), default="blocked")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SustainabilityLedger(Base):
    __tablename__ = "sustainability_ledgers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    product_key: Mapped[str] = mapped_column(String(100))
    workload_type: Mapped[str] = mapped_column(String(40))
    region: Mapped[str] = mapped_column(String(40))
    energy_wh: Mapped[float] = mapped_column(Float)
    carbon_grams: Mapped[float] = mapped_column(Float)
    water_ml: Mapped[float] = mapped_column(Float)
    cost_cents: Mapped[int] = mapped_column(Integer)
    methodology: Mapped[dict] = mapped_column(JSON, default=dict)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class GovernanceProposal(Base):
    __tablename__ = "governance_proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    charter_rule: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    quorum_weight: Mapped[float] = mapped_column(Float)
    veto_conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    conflict_disclosures: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="voting")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class GovernanceVote(Base):
    __tablename__ = "governance_votes"
    __table_args__ = (UniqueConstraint("proposal_id", "voter_organization_id", name="uq_governance_vote"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("governance_proposals.id", ondelete="CASCADE"))
    voter_organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    choice: Mapped[str] = mapped_column(String(12))
    weight: Mapped[float] = mapped_column(Float)
    conflict_disclosed: Mapped[bool] = mapped_column(Boolean, default=False)
    signature: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
