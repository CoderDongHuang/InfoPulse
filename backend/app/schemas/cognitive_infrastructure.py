from datetime import datetime
from pydantic import BaseModel,Field
class CertificationCreate(BaseModel): standard_version:str;proof_type:str;implementations:list[dict]=Field(min_length=3);test_vectors:list[dict]=Field(min_length=1);revocation_tests:list[dict]=Field(default_factory=list)
class ConstitutionUpgradeCreate(BaseModel): constitution_key:str;from_version:str;to_version:str;current_rules:dict;proposed_rules:dict;impact_simulation:dict;vote:dict;effective_at:datetime;rollback_plan:dict
class ArchiveCreate(BaseModel): object_type:str;object_id:str;content_hash:str=Field(min_length=64,max_length=64);algorithm:str;timestamp_witnesses:list[str]=Field(min_length=1);historical_roots:list[str]=Field(default_factory=list)
class PublicSignalCreate(BaseModel): signal_key:str;metric:dict;sources:list[dict]=Field(min_length=2);allowed_purposes:list[str]=Field(min_length=1);regions:list[str]=Field(min_length=1)
class EpistemicCreate(BaseModel): claim_id:str;evidence_graph:dict[str,list[str]];source_families:dict[str,str];agent_outputs:list[dict];narrative_signals:dict=Field(default_factory=dict)
class ClearingCreate(BaseModel): network_key:str;assets:dict[str,int];obligations:list[dict];prices:dict[str,float];liquidity_buffer:dict[str,int];stress_shock:float=Field(default=.2,ge=0,le=1)
class AllocationCreate(BaseModel): resource_key:str;available_capacity:float=Field(gt=0);requests:list[dict]=Field(min_length=1)
class ScenarioCreate(BaseModel): name:str;horizon_years:int=Field(ge=10);drivers:dict[str,list[float]];interventions:list[dict]=Field(default_factory=list)
class CommitmentCreate(BaseModel): commitment_key:str;beneficiaries:list[str]=Field(min_length=1);target_year:int;baseline:dict;current_state:dict;cost_transfers:dict;externalities:dict
class StackBuildCreate(BaseModel): release_version:str;source_digest:str=Field(min_length=64,max_length=64);build_manifest:dict;artifact_digest:str=Field(min_length=64,max_length=64);reproduction_digest:str=Field(min_length=64,max_length=64);hardware_root:dict;offline_capabilities:list[str]
class StackUpgradeCreate(BaseModel): build_id:str;from_version:str;to_version:str;package_hash:str=Field(min_length=64,max_length=64);signature_valid:bool;offline_test:dict;rollback_proof:dict
