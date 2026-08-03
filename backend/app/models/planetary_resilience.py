"""Stage 26 planetary intelligence resilience and trusted autonomous economy."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def uid() -> str: return str(uuid.uuid4())
def now() -> datetime: return datetime.now(timezone.utc)


class ProofMeshEnvelope(Base):
    __tablename__="proof_mesh_envelopes";__table_args__=(UniqueConstraint("organization_id","idempotency_key",name="uq_proof_mesh_envelope"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);organization_id:Mapped[str]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);recipient_organization_id:Mapped[str]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);decision_proof_id:Mapped[str]=mapped_column(ForeignKey("decision_proofs.id",ondelete="RESTRICT"));dependency_ids:Mapped[list]=mapped_column(JSON,default=list);trust_signatures:Mapped[list]=mapped_column(JSON,default=list);trust_threshold:Mapped[int]=mapped_column(Integer);idempotency_key:Mapped[str]=mapped_column(String(160));mesh_hash:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default="available");revoked_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True));created_by:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="RESTRICT"))


class PolicyProofRegistry(Base):
    __tablename__="policy_proof_registry";__table_args__=(UniqueConstraint("organization_id","policy_key","version",name="uq_policy_proof_version"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);organization_id:Mapped[str]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);policy_key:Mapped[str]=mapped_column(String(100));version:Mapped[str]=mapped_column(String(40));model_check_id:Mapped[str]=mapped_column(ForeignKey("policy_model_checks.id",ondelete="RESTRICT"));compatibility:Mapped[dict]=mapped_column(JSON,default=dict);counterexamples:Mapped[list]=mapped_column(JSON,default=list);transparency_root:Mapped[str]=mapped_column(String(64));registry_signature:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default="active");created_by:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="RESTRICT"))


class PostQuantumMigration(Base):
    __tablename__="post_quantum_migrations"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);organization_id:Mapped[str]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);subject_type:Mapped[str]=mapped_column(String(40));subject_id:Mapped[str]=mapped_column(String(80));classical_algorithm:Mapped[str]=mapped_column(String(40));pq_algorithm:Mapped[str]=mapped_column(String(40));classical_fingerprint:Mapped[str]=mapped_column(String(64));pq_fingerprint:Mapped[str]=mapped_column(String(64));hybrid_signature:Mapped[dict]=mapped_column(JSON,default=dict);historical_resignatures:Mapped[list]=mapped_column(JSON,default=list);status:Mapped[str]=mapped_column(String(20),default="migrated");created_by:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="RESTRICT"))


class PlanetaryTwinRun(Base):
    __tablename__="planetary_twin_runs"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);organization_id:Mapped[str]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);domains:Mapped[list]=mapped_column(JSON,default=list);topology:Mapped[dict]=mapped_column(JSON,default=dict);shocks:Mapped[list]=mapped_column(JSON,default=list);cascade_path:Mapped[list]=mapped_column(JSON,default=list);recovery_plan:Mapped[list]=mapped_column(JSON,default=list);systemic_score:Mapped[float]=mapped_column(Float);replay_hash:Mapped[str]=mapped_column(String(64));status:Mapped[str]=mapped_column(String(20),default="completed");created_by:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="RESTRICT"))


class AgentConstitutionRun(Base):
    __tablename__="agent_constitution_runs"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);organization_id:Mapped[str]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);collective_run_id:Mapped[str]=mapped_column(ForeignKey("agent_collective_runs.id",ondelete="CASCADE"));constitution:Mapped[dict]=mapped_column(JSON,default=dict);proposed_action:Mapped[dict]=mapped_column(JSON,default=dict);vote:Mapped[dict]=mapped_column(JSON,default=dict);human_veto:Mapped[dict]=mapped_column(JSON,default=dict);violations:Mapped[list]=mapped_column(JSON,default=list);execution_proof:Mapped[dict]=mapped_column(JSON,default=dict);status:Mapped[str]=mapped_column(String(20),default="blocked");created_by:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="RESTRICT"))


class CrisisResourceListing(Base):
    __tablename__="crisis_resource_listings"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);organization_id:Mapped[str]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);resource_type:Mapped[str]=mapped_column(String(40));region:Mapped[str]=mapped_column(String(40));capacity:Mapped[float]=mapped_column(Float);unit_price_cents:Mapped[int]=mapped_column(Integer);priority_floor:Mapped[int]=mapped_column(Integer,default=0);sla:Mapped[dict]=mapped_column(JSON,default=dict);status:Mapped[str]=mapped_column(String(20),default="available");created_by:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="RESTRICT"))


class CrisisResourceTrade(Base):
    __tablename__="crisis_resource_trades";__table_args__=(UniqueConstraint("buyer_organization_id","idempotency_key",name="uq_crisis_trade"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);organization_id:Mapped[str]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);buyer_organization_id:Mapped[str]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"));listing_id:Mapped[str]=mapped_column(ForeignKey("crisis_resource_listings.id",ondelete="RESTRICT"));quantity:Mapped[float]=mapped_column(Float);priority:Mapped[int]=mapped_column(Integer);amount_cents:Mapped[int]=mapped_column(Integer);idempotency_key:Mapped[str]=mapped_column(String(160));receipt:Mapped[dict]=mapped_column(JSON,default=dict);settlement:Mapped[dict]=mapped_column(JSON,default=dict);status:Mapped[str]=mapped_column(String(20),default="allocated");created_by:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="RESTRICT"))


class AutonomousInsurancePolicy(Base):
    __tablename__="autonomous_insurance_policies"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);organization_id:Mapped[str]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);subject_type:Mapped[str]=mapped_column(String(40));subject_id:Mapped[str]=mapped_column(String(80));risk_signals:Mapped[dict]=mapped_column(JSON,default=dict);premium_cents:Mapped[int]=mapped_column(Integer);coverage_limit_cents:Mapped[int]=mapped_column(Integer);reserve_cents:Mapped[int]=mapped_column(Integer);trigger:Mapped[dict]=mapped_column(JSON,default=dict);claims:Mapped[list]=mapped_column(JSON,default=list);status:Mapped[str]=mapped_column(String(20),default="active");created_by:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="RESTRICT"))


class VerifiableMemoryTransfer(Base):
    __tablename__="verifiable_memory_transfers"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);organization_id:Mapped[str]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);recipient_organization_id:Mapped[str]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"));memory_record_id:Mapped[str]=mapped_column(ForeignKey("memory_governance_records.id",ondelete="RESTRICT"));purpose:Mapped[str]=mapped_column(String(100));source_region:Mapped[str]=mapped_column(String(40));target_region:Mapped[str]=mapped_column(String(40));retention_until:Mapped[datetime]=mapped_column(DateTime(timezone=True));target_inclusion_proof:Mapped[dict]=mapped_column(JSON,default=dict);source_erasure_proof:Mapped[dict]=mapped_column(JSON,default=dict);status:Mapped[str]=mapped_column(String(20),default="blocked");created_by:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="RESTRICT"))


class EdgeMeshMessage(Base):
    __tablename__="edge_mesh_messages";__table_args__=(UniqueConstraint("organization_id","node_id","sequence",name="uq_edge_mesh_sequence"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);organization_id:Mapped[str]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);node_id:Mapped[str]=mapped_column(String(80));sequence:Mapped[int]=mapped_column(Integer);vector_clock:Mapped[dict]=mapped_column(JSON,default=dict);payload_hash:Mapped[str]=mapped_column(String(64));signature:Mapped[str]=mapped_column(String(64));previous_hash:Mapped[str]=mapped_column(String(64),default="");chain_hash:Mapped[str]=mapped_column(String(64));online:Mapped[bool]=mapped_column(Boolean,default=False);status:Mapped[str]=mapped_column(String(20),default="queued");created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class PublicInterestAudit(Base):
    __tablename__="public_interest_audits"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);organization_id:Mapped[str]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True);scope:Mapped[str]=mapped_column(String(80));metrics:Mapped[dict]=mapped_column(JSON,default=dict);fairness:Mapped[dict]=mapped_column(JSON,default=dict);externalities:Mapped[dict]=mapped_column(JSON,default=dict);resource_allocation:Mapped[dict]=mapped_column(JSON,default=dict);public_commitment:Mapped[str]=mapped_column(String(64));observer_proofs:Mapped[list]=mapped_column(JSON,default=list);status:Mapped[str]=mapped_column(String(20),default="published");created_by:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="RESTRICT"));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
