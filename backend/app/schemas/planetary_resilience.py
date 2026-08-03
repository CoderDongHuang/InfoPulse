from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ProofMeshCreate(BaseModel):
    recipient_organization_id:str;decision_proof_id:str;dependency_ids:list[str]=Field(default_factory=list);trust_signatures:list[str]=Field(min_length=1);trust_threshold:int=Field(ge=1);idempotency_key:str=Field(min_length=8,max_length=160)
class PolicyRegistryCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    policy_key:str;version:str;model_check_id:str;compatibility:dict;counterexamples:list[dict]=Field(default_factory=list);transparency_root:str=Field(min_length=64,max_length=64)
class PQMigrationCreate(BaseModel):
    subject_type:str;subject_id:str;classical_algorithm:str;pq_algorithm:str;classical_fingerprint:str=Field(min_length=64,max_length=64);pq_fingerprint:str=Field(min_length=64,max_length=64);historical_proofs:list[dict]=Field(default_factory=list)
class PlanetaryTwinCreate(BaseModel): domains:list[str]=Field(min_length=5);topology:dict[str,list[str]];shocks:list[str]=Field(min_length=1)
class ConstitutionCreate(BaseModel): collective_run_id:str;constitution:dict;proposed_action:dict;vote:dict;human_veto:dict=Field(default_factory=dict)
class ResourceListingCreate(BaseModel): resource_type:str;region:str;capacity:float=Field(gt=0);unit_price_cents:int=Field(ge=0);priority_floor:int=Field(default=0,ge=0);sla:dict=Field(default_factory=dict)
class ResourceTradeCreate(BaseModel): listing_id:str;quantity:float=Field(gt=0);priority:int=Field(ge=0);idempotency_key:str=Field(min_length=8,max_length=160)
class TradeTransition(BaseModel): action:str=Field(pattern="^(deliver|refund|settle)$");receipt:dict=Field(default_factory=dict)
class InsuranceCreate(BaseModel): subject_type:str;subject_id:str;risk_signals:dict[str,float];base_limit_cents:int=Field(gt=0);trigger:dict
class InsuranceClaim(BaseModel): event:dict;loss_cents:int=Field(gt=0)
class MemoryTransferCreate(BaseModel): recipient_organization_id:str;memory_record_id:str;purpose:str;source_region:str;target_region:str;retention_until:datetime
class EdgeMessageCreate(BaseModel): node_id:str;sequence:int=Field(ge=1);vector_clock:dict[str,int];payload:dict;online:bool=False
class PublicAuditCreate(BaseModel): scope:str;metrics:dict;fairness:dict;externalities:dict;resource_allocation:dict;observer_signatures:list[str]=Field(min_length=1)
