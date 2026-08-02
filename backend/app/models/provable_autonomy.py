"""Stage 25 provable autonomy and global continuity models."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def uid() -> str: return str(uuid.uuid4())
def now() -> datetime: return datetime.now(timezone.utc)


class DecisionProof(Base):
    __tablename__ = "decision_proofs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    action_id: Mapped[str] = mapped_column(String(80), index=True)
    objective: Mapped[dict] = mapped_column(JSON, default=dict)
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_hashes: Mapped[list] = mapped_column(JSON, default=list)
    policy_hash: Mapped[str] = mapped_column(String(64))
    result_hash: Mapped[str] = mapped_column(String(64))
    proof: Mapped[dict] = mapped_column(JSON, default=dict)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="blocked")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PolicyModelCheck(Base):
    __tablename__ = "policy_model_checks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    policy_key: Mapped[str] = mapped_column(String(100))
    states: Mapped[list] = mapped_column(JSON, default=list)
    transitions: Mapped[list] = mapped_column(JSON, default=list)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    violations: Mapped[list] = mapped_column(JSON, default=list)
    counterexample: Mapped[list] = mapped_column(JSON, default=list)
    replay_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="review")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class RegionReplica(Base):
    __tablename__ = "region_replicas"
    __table_args__ = (UniqueConstraint("organization_id", "replica_key", "region", name="uq_region_replica"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    replica_key: Mapped[str] = mapped_column(String(100))
    region: Mapped[str] = mapped_column(String(40))
    vector_clock: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    recovery_point: Mapped[str] = mapped_column(String(64))
    healthy: Mapped[bool] = mapped_column(Boolean, default=True)
    failover_priority: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class RegulatoryPartition(Base):
    __tablename__ = "regulatory_partitions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    product_key: Mapped[str] = mapped_column(String(100))
    region: Mapped[str] = mapped_column(String(40))
    rules: Mapped[dict] = mapped_column(JSON, default=dict)
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    legal_data_paths: Mapped[list] = mapped_column(JSON, default=list)
    conflicts: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class MemoryGovernanceRecord(Base):
    __tablename__ = "memory_governance_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    memory_key: Mapped[str] = mapped_column(String(120))
    allowed_purposes: Mapped[list] = mapped_column(JSON, default=list)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64))
    contamination_score: Mapped[float] = mapped_column(Float, default=0)
    quarantine_reason: Mapped[str] = mapped_column(Text, default="")
    erasure_proof: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class AgentCollectiveRun(Base):
    __tablename__ = "agent_collective_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    agent_ids: Mapped[list] = mapped_column(JSON, default=list)
    delegation_graph: Mapped[dict] = mapped_column(JSON, default=dict)
    tool_grants: Mapped[dict] = mapped_column(JSON, default=dict)
    budget_cents: Mapped[int] = mapped_column(Integer)
    spent_cents: Mapped[int] = mapped_column(Integer, default=0)
    communication_edges: Mapped[list] = mapped_column(JSON, default=list)
    collusion_score: Mapped[float] = mapped_column(Float, default=0)
    violations: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="blocked")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class PredictionMarket(Base):
    __tablename__ = "prediction_markets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text)
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    liquidity_cents: Mapped[int] = mapped_column(Integer)
    aggregate_probability: Mapped[float] = mapped_column(Float, default=.5)
    manipulation_score: Mapped[float] = mapped_column(Float, default=0)
    outcome: Mapped[bool | None] = mapped_column(Boolean)
    settlement: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class ForecastPosition(Base):
    __tablename__ = "forecast_positions"
    __table_args__ = (UniqueConstraint("market_id", "forecaster_organization_id", name="uq_forecast_position"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("prediction_markets.id", ondelete="CASCADE"))
    forecaster_organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    probability: Mapped[float] = mapped_column(Float)
    stake_cents: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float, default=0)
    payout_cents: Mapped[int] = mapped_column(Integer, default=0)


class DisasterKernelSnapshot(Base):
    __tablename__ = "disaster_kernel_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    unavailable_dependencies: Mapped[list] = mapped_column(JSON, default=list)
    available_capabilities: Mapped[list] = mapped_column(JSON, default=list)
    offline_identity: Mapped[dict] = mapped_column(JSON, default=dict)
    audit_root: Mapped[str] = mapped_column(String(64))
    manual_takeover: Mapped[dict] = mapped_column(JSON, default=dict)
    gate_status: Mapped[str] = mapped_column(String(20), default="blocked")
    tested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class GreenSchedule(Base):
    __tablename__ = "green_schedules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    workload_key: Mapped[str] = mapped_column(String(100))
    residency_region: Mapped[str] = mapped_column(String(40))
    selected_region: Mapped[str] = mapped_column(String(40), default="")
    selected_window: Mapped[str] = mapped_column(String(80), default="")
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)
    candidates: Mapped[list] = mapped_column(JSON, default=list)
    resource_proof: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="blocked")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class LiabilitySettlement(Base):
    __tablename__ = "liability_settlements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    responsibility_event_id: Mapped[str] = mapped_column(ForeignKey("responsibility_events.id", ondelete="RESTRICT"))
    arbitration_case_id: Mapped[str | None] = mapped_column(ForeignKey("arbitration_cases.id", ondelete="SET NULL"))
    loss_cents: Mapped[int] = mapped_column(Integer)
    compensation_cents: Mapped[int] = mapped_column(Integer)
    recovery_cents: Mapped[int] = mapped_column(Integer)
    reserve_cents: Mapped[int] = mapped_column(Integer)
    allocation: Mapped[dict] = mapped_column(JSON, default=dict)
    reconciliation: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="calculated")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
