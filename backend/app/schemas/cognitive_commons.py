from pydantic import BaseModel,Field
class ConsensusCreate(BaseModel):proof_id:str;nodes:list[str]=Field(min_length=4);votes:list[dict];fault_tolerance:int=Field(default=1,ge=0)
class ConstitutionProtocolCreate(BaseModel):action_key:str;constitutions:list[dict]=Field(min_length=2);required_permission:str;amendment:dict=Field(default_factory=dict)
class EvidencePreserveCreate(BaseModel):archive_id:str;retired_algorithm:str;new_algorithm:str;previous_proof:dict;timestamp_witnesses:list[str]=Field(min_length=2)
class CausalValidationCreate(BaseModel):signal_id:str;experiments:list[dict]=Field(min_length=3);counterfactuals:list[dict]=Field(default_factory=list)
class DissentMarketCreate(BaseModel):claim_id:str;positions:list[dict]=Field(min_length=2);reward_pool_cents:int=Field(gt=0)
class TreasuryCreate(BaseModel):treasury_key:str;opening_cents:int=Field(ge=0);revenues:list[dict];grants:list[dict];expenses:list[dict];reserve_cents:int=Field(ge=0)
class AppealCreate(BaseModel):allocation_id:str;appellant_key:str;evidence:list[dict]=Field(min_length=1);claimed_amount:float=Field(ge=0);compensation_rate_cents:float=Field(default=100,ge=0)
class CenturyScenarioCreate(BaseModel):name:str;horizon_years:int=Field(ge=100);domains:dict[str,list[float]];interactions:list[dict];interventions:list[dict]=Field(default_factory=list)
class SafetyValveCreate(BaseModel):valve_key:str;capability_limits:dict;pause_signatures:list[str];pause_threshold:int=Field(ge=2);degraded_capabilities:list[str];recovery_approvals:list[str]=Field(default_factory=list);drill_evidence:dict=Field(default_factory=dict)
class FederatedReleaseCreate(BaseModel):build_id:str;release_version:str;mirrors:list[dict]=Field(min_length=2);offline_patch:dict;node_attestations:list[dict]=Field(min_length=2);compatibility:dict
