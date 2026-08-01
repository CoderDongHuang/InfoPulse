from datetime import datetime
from pydantic import BaseModel,Field,model_validator
class CredentialLeaseCreate(BaseModel): installation_id:str;provider:str;secret_reference:str=Field(min_length=3,max_length=500);secret_fingerprint:str=Field(min_length=16,max_length=64);region:str="global";egress_policy:dict=Field(default_factory=dict);expires_at:datetime|None=None
class ApprovalRunCreate(BaseModel): flow_id:str;subject_type:str;subject_id:str;idempotency_key:str=Field(min_length=8,max_length=160);context:dict=Field(default_factory=dict)
class ApprovalDecision(BaseModel): node_id:str;decision:str=Field(pattern="^(approved|rejected)$");signature_nonce:str=Field(min_length=8);delegate_to_id:str|None=None
class CausalExperimentCreate(BaseModel): name:str;metric_key:str;method:str="difference_in_differences";treatment:dict;control:dict;confounders:list[str]=Field(default_factory=list);window:dict;minimum_sample:int=Field(ge=20);power:float=Field(ge=0,le=1)
class LedgerCreate(BaseModel): entry_type:str;department:str="unallocated";amount_cents:int;currency:str=Field(default="CNY",min_length=3,max_length=3);external_reference:str;provider:str="internal";metadata_json:dict=Field(default_factory=dict)
class BillingDocumentCreate(BaseModel): document_type:str;period:str=Field(pattern=r"^\d{4}-\d{2}$");amount_cents:int=Field(ge=0);tax_cents:int=Field(default=0,ge=0);currency:str="CNY";provider_reference:str=""
class PaymentReconcile(BaseModel): provider:str;external_reference:str;provider_reference:str;amount_cents:int;currency:str="CNY"
class PrivacyBudgetCreate(BaseModel): dataset_key:str;period:str=Field(pattern=r"^\d{4}-\d{2}$");epsilon_limit:float=Field(gt=0);delta:float=Field(default=.00001,gt=0,lt=1);minimum_cohort:int=Field(default=10,ge=5)
class PrivacyQuery(BaseModel): dataset_key:str;query:dict;epsilon_cost:float=Field(gt=0);cohort_size:int=Field(ge=1);similar_query_count:int=Field(default=0,ge=0)
class PolicyCreate(BaseModel): key:str=Field(pattern=r"^[a-z0-9_-]{2,80}$");name:str;rules:dict;test_cases:list[dict]=Field(default_factory=list)
class PolicyPublish(BaseModel): version:int=Field(ge=1);canary_percent:int=Field(ge=0,le=100)
class RecoveryDrillCreate(BaseModel): region:str;drill_type:str;rpo_target_minutes:int=Field(gt=0);rto_target_minutes:int=Field(gt=0);actual_rpo_minutes:int|None=Field(default=None,ge=0);actual_rto_minutes:int|None=Field(default=None,ge=0);evidence:dict=Field(default_factory=dict);isolation_verified:bool=False
class ComplianceControlCreate(BaseModel): framework:str=Field(pattern="^(SOC2|ISO27001)$");control_key:str;title:str;owner_id:str
class ComplianceEvidenceCreate(BaseModel): control_id:str;evidence_type:str;locator:str;checksum:str=Field(min_length=32,max_length=64);expires_at:datetime|None=None;metadata_json:dict=Field(default_factory=dict)
class SafetyEvaluationCreate(BaseModel): target_type:str;target_id:str;scenario:str;results:dict=Field(default_factory=dict);permission_drift:bool=False;rollback_verified:bool=False;score:float=Field(ge=0,le=100)
