from pydantic import BaseModel,Field,model_validator
class AgreementCreate(BaseModel):partner_organization_id:str;purpose:str;allowed_metrics:list[str];regions:list[str]=Field(default_factory=list);minimum_cohort:int=Field(default=10,ge=5)
class EnvelopeCreate(BaseModel):agreement_id:str;metric_key:str;aggregate:dict;evidence_summary:dict=Field(default_factory=dict);privacy:dict;idempotency_key:str=Field(min_length=8,max_length=160)
class ProvenanceCreate(BaseModel):object_type:str;object_id:str;version:str="";content_hash:str=Field(min_length=64,max_length=64);metadata_json:dict=Field(default_factory=dict);parent_ids:list[str]=Field(default_factory=list);relation:str="derived_from"
class DataContractCreate(BaseModel):dataset_key:str;purpose:str;allowed_uses:list[str];regions:list[str];derivative_rights:str="restricted"
class SupplyArtifactCreate(BaseModel):artifact_type:str=Field(pattern="^(model|agent|tool|prompt)$");key:str;version:str;manifest:dict;sbom:list[dict]=Field(default_factory=list);vendor_risk:float=Field(ge=0,le=1);attestation:dict=Field(default_factory=dict)
class ProductCreate(BaseModel):key:str;name:str;description:str="";license_terms:dict;quality_sla:dict;price_cents:int=Field(ge=0);currency:str="CNY";revenue_share_percent:float=Field(default=80,ge=0,le=100)
class OrderCreate(BaseModel):product_id:str;idempotency_key:str=Field(min_length=8,max_length=160);provider_reference:str
class OrderTransition(BaseModel):action:str=Field(pattern="^(deliver|settle|refund|dispute)$");receipt:dict=Field(default_factory=dict);reason:str=""
class FederatedComputeCreate(BaseModel):agreement_id:str;computation_type:str=Field(pattern="^(secure_sum|secure_average|tee_query)$");participants:list[str]=Field(min_length=2);privacy_allocation:dict;attestation:dict=Field(default_factory=dict);inputs:list[float]=Field(default_factory=list)
class ResponsibilityCreate(BaseModel):subject_type:str;subject_id:str;event_type:str;payload:dict
class RegulatoryPackCreate(BaseModel):key:str;version:int=Field(ge=1);industry:str;region:str;rules:dict;rollback_of_version:int|None=None
class TrustUpdate(BaseModel):subject_type:str;subject_id:str;quality:float=Field(ge=0,le=100);reliability:float=Field(ge=0,le=100);abuse_penalty:float=Field(default=0,ge=0,le=100)
class AbuseCreate(BaseModel):subject_type:str;subject_id:str;category:str;evidence:dict
class DrillCreate(BaseModel):scenario:str=Field(pattern="^(vendor_exit|regional_outage|key_compromise|data_poisoning|settlement_outage)$");participants:list[str];expected_controls:list[str];evidence:dict=Field(default_factory=dict);containment_minutes:int|None=Field(default=None,ge=0);recovery_minutes:int|None=Field(default=None,ge=0)
