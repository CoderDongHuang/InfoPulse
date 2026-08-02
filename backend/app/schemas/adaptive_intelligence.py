from pydantic import BaseModel, Field


class RolloutCreate(BaseModel):
    protocol_key: str
    from_version: str
    to_version: str
    compatibility_matrix: dict
    canary_percent: int = Field(default=5, ge=1, le=100)
    health: dict = Field(default_factory=dict)


class PolicySynthesisCreate(BaseModel):
    regulatory_update_id: str | None = None
    candidate_policy: dict
    formal_result: dict
    sandbox_diff: dict
    approver_ids: list[str] = Field(default_factory=list)


class TransparencyAppend(BaseModel):
    object_type: str = Field(pattern="^(model|policy|proof|responsibility)$")
    object_id: str
    payload: dict
    witness_signatures: list[str] = Field(default_factory=list)


class TwinRunCreate(BaseModel):
    scenario_type: str = Field(pattern="^(regional_outage|vendor_exit|sanctions|fx_shock|information_poisoning)$")
    topology: dict[str, list[str]]
    shocks: list[str] = Field(min_length=1)


class MarketControlCreate(BaseModel):
    market_key: str
    liquidity_limit_cents: int = Field(gt=0)
    collateral_haircut: float = Field(ge=0, le=1)
    anomaly_threshold: float = Field(gt=0, le=1)
    observed_anomaly: float = Field(default=0, ge=0, le=1)
    stress_loss_cents: int = Field(default=0, ge=0)


class SovereignRouteCreate(BaseModel):
    request_key: str
    residency_region: str
    constraints: dict = Field(default_factory=dict)
    candidates: list[dict] = Field(min_length=1)


class IncidentCreate(BaseModel):
    signal: dict
    playbooks: dict[str, list[str]]


class AssuranceCreate(BaseModel):
    control_id: str
    evidence_age_hours: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    max_evidence_age_hours: int = Field(default=24, ge=1)
    minimum_confidence: float = Field(default=.8, ge=0, le=1)


class SustainabilityCreate(BaseModel):
    product_key: str
    workload_type: str
    region: str
    compute_wh: float = Field(ge=0)
    storage_gb_hours: float = Field(ge=0)
    transfer_gb: float = Field(ge=0)
    carbon_factor: float = Field(ge=0)
    water_factor: float = Field(ge=0)
    cost_cents: int = Field(ge=0)


class ProposalCreate(BaseModel):
    title: str
    charter_rule: str
    payload: dict
    quorum_weight: float = Field(gt=0)
    veto_conditions: dict = Field(default_factory=dict)
    conflict_disclosures: list[dict] = Field(default_factory=list)


class VoteCreate(BaseModel):
    choice: str = Field(pattern="^(yes|no|abstain|veto)$")
    weight: float = Field(gt=0)
    conflict_disclosed: bool = False


class ProposalFinalize(BaseModel):
    eligible_weight: float = Field(gt=0)
