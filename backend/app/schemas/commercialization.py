from pydantic import BaseModel, Field, HttpUrl, model_validator

class TemplateCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,79}$"); name: str = Field(min_length=2,max_length=160); description: str = ""; visibility: str = "private"; definition: dict = Field(default_factory=dict); change_note: str = "Initial version"
class TemplateVersionCreate(BaseModel): definition: dict; change_note: str = Field(min_length=2,max_length=500)
class ApprovalFlowCreate(BaseModel):
    name: str = Field(min_length=2,max_length=160); trigger: str; graph: dict; enabled: bool = True
    @model_validator(mode="after")
    def valid_graph(self):
        nodes=self.graph.get("nodes",[]); edges=self.graph.get("edges",[]); ids={n.get("id") for n in nodes}
        if not nodes or not all(e.get("from") in ids and e.get("to") in ids for e in edges): raise ValueError("Approval graph contains invalid nodes or edges")
        return self
class ConnectorExecute(BaseModel):
    installation_id: str; provider: str = Field(pattern="^(slack|teams|feishu|dingtalk)$"); webhook_url: HttpUrl; message: str = Field(min_length=1,max_length=12000); action_id: str|None=None; idempotency_key: str = Field(min_length=8,max_length=160)
class MetricCollectorCreate(BaseModel): metric_id: str; source_type: str = Field(pattern="^(webhook|api|manual|product_usage)$"); config: dict = Field(default_factory=dict); enabled: bool=True
class AttributionAuditCreate(BaseModel): measurement_id: str; method: str; assumptions: list[str]=Field(default_factory=list); evidence: dict=Field(default_factory=dict); confidence: float=Field(ge=0,le=1); conclusion: str="correlation_only"
class SLAPolicyCreate(BaseModel): name: str=Field(min_length=2,max_length=160); target_type: str; target_minutes: int=Field(gt=0); warning_minutes: int=Field(gt=0); escalation_steps: list[dict]=Field(default_factory=list); enabled: bool=True
class EntitlementUpdate(BaseModel): plan_key: str; limits: dict[str,int]=Field(default_factory=dict); feature_flags: dict[str,bool]=Field(default_factory=dict); status: str="active"
class UsageRecord(BaseModel): feature: str; quantity: int=Field(gt=0); cost_cents: int=Field(default=0,ge=0); dimensions: dict=Field(default_factory=dict)
class BenchmarkPublish(BaseModel): metric_key: str; cohort: str; sample_size: int=Field(ge=5); aggregate_value: float; k_anonymity: int=Field(default=5,ge=5)
