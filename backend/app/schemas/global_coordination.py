from pydantic import BaseModel, Field


class NodeCreate(BaseModel):
    node_key: str
    cloud: str
    region: str
    protocol_versions: list[str] = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    identity_issuer: str
    identity_fingerprint: str = Field(min_length=64, max_length=64)


class NegotiationCreate(BaseModel):
    local_node_id: str
    remote_node_id: str
    idempotency_key: str = Field(min_length=8, max_length=160)
    presented_identity_fingerprint: str = Field(min_length=64, max_length=64)


class ProofCreate(BaseModel):
    proof_type: str = Field(pattern="^(provenance|tee|model_signature|responsibility_chain)$")
    subject_type: str
    subject_id: str
    expected_hash: str = Field(min_length=64, max_length=64)
    observed_hash: str = Field(min_length=64, max_length=64)
    signature_valid: bool
    chain_valid: bool
    attestation: dict = Field(default_factory=dict)


class ContractCreate(BaseModel):
    counterparty_organization_id: str
    proposal: dict
    constraints: dict
    budget_cents: int = Field(ge=0)
    privacy_epsilon: float = Field(gt=0)


class SubscriptionCreate(BaseModel):
    pack_key: str
    industry: str
    regions: list[str] = Field(min_length=1)


class RegulatoryUpdateCreate(BaseModel):
    subscription_id: str
    version: int = Field(ge=1)
    delta: dict
    existing_rules: dict = Field(default_factory=dict)
    emergency: bool = False


class RiskCreate(BaseModel):
    risk_type: str = Field(pattern="^(concentration|cascade|market_manipulation|data_poisoning)$")
    subject_ids: list[str] = Field(min_length=1)
    factors: dict[str, float]
    threshold: float = Field(default=0.7, ge=0, le=1)


class ObservationCreate(BaseModel):
    control_id: str
    observed_state: dict
    expected_state: dict


class ArbitrationCreate(BaseModel):
    dispute_id: str
    evidence: list[dict] = Field(min_length=1)
    reproduction: dict = Field(default_factory=dict)
    arbitrator_organization_id: str | None = None
    bond_cents: int = Field(default=0, ge=0)


class ArbitrationDecision(BaseModel):
    outcome: str = Field(pattern="^(upheld|rejected|partial)$")
    reason_codes: list[str]
    recovery_steps: list[str] = Field(default_factory=list)


class EvaluationCreate(BaseModel):
    artifact_id: str
    participants: list[str] = Field(min_length=2)
    suite_version: str
    participant_metrics: list[dict[str, float]] = Field(min_length=2)
    bias_summary: dict = Field(default_factory=dict)
    red_team_summary: dict = Field(default_factory=dict)
    attestation: dict = Field(default_factory=dict)


class SettlementCreate(BaseModel):
    order_id: str
    external_reference: str
    source_currency: str = Field(min_length=3, max_length=3)
    target_currency: str = Field(min_length=3, max_length=3)
    source_amount_cents: int = Field(gt=0)
    fx_rate: float = Field(gt=0)
    tax_jurisdiction: str
    withholding_cents: int = Field(ge=0)
    escrow_cents: int = Field(ge=0)
    payout_cents: int = Field(ge=0)


class CrisisRoomCreate(BaseModel):
    name: str
    region_scope: list[str] = Field(min_length=1)
    classification: str
    commander_organization_id: str
    participants: list[str] = Field(min_length=2)


class CrisisCommandCreate(BaseModel):
    command_type: str
    classification: str
    payload: dict
