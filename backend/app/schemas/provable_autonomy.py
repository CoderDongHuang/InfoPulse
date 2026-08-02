from datetime import datetime
from pydantic import BaseModel, Field


class DecisionProofCreate(BaseModel):
    action_id: str; objective: dict; constraints: dict; evidence: list[dict] = Field(min_length=1); policy: dict; result: dict


class ModelCheckCreate(BaseModel):
    policy_key: str; states: list[str] = Field(min_length=1); transitions: list[dict]; properties: dict


class ReplicaCreate(BaseModel):
    replica_key: str; region: str; vector_clock: dict[str, int]; state: dict; healthy: bool = True; failover_priority: int = Field(default=0, ge=0)


class ReplicaMerge(BaseModel):
    replicas: list[dict] = Field(min_length=3)


class RegulatoryPartitionCreate(BaseModel):
    product_key: str; region: str; rules: dict; requested_capabilities: list[str]; data_paths: list[dict]


class MemoryCreate(BaseModel):
    memory_key: str; allowed_purposes: list[str] = Field(min_length=1); expires_at: datetime; content_hash: str = Field(min_length=64, max_length=64); contamination_score: float = Field(default=0, ge=0, le=1)


class MemoryErase(BaseModel): reason: str


class CollectiveCreate(BaseModel):
    agent_ids: list[str] = Field(min_length=1); delegation_graph: dict[str, list[str]]; tool_grants: dict[str, list[str]]; budget_cents: int = Field(gt=0); spent_cents: int = Field(ge=0); communication_edges: list[dict] = Field(default_factory=list); limits: dict


class MarketCreate(BaseModel): question: str; closes_at: datetime; liquidity_cents: int = Field(gt=0)
class ForecastCreate(BaseModel): probability: float = Field(gt=0, lt=1); stake_cents: int = Field(gt=0)
class MarketSettle(BaseModel): outcome: bool


class DisasterTestCreate(BaseModel): unavailable_dependencies: list[str]; available_capabilities: list[str]; offline_identity: dict; manual_takeover: dict


class GreenScheduleCreate(BaseModel):
    workload_key: str; residency_region: str; constraints: dict; candidates: list[dict] = Field(min_length=1)


class LiabilityCreate(BaseModel):
    responsibility_event_id: str; arbitration_case_id: str | None = None; loss_cents: int = Field(ge=0); compensation_cents: int = Field(ge=0); recovery_cents: int = Field(ge=0); reserve_cents: int = Field(ge=0); responsible_parties: dict[str, float]
