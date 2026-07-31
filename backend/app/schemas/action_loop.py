from datetime import datetime
from pydantic import BaseModel, Field
class ActionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=300); description: str = ""; owner_id: str; event_id: str|None = None; scenario_id: str|None = None; decision_room_id: str|None = None; evidence_content_ids: list[str] = Field(default_factory=list); risk_level: str = "medium"; due_at: datetime|None = None; sla_minutes: int|None = Field(default=None, ge=1); budget_cents: int = Field(default=0, ge=0); stop_conditions: list[str] = Field(default_factory=list); dependency_ids: list[str] = Field(default_factory=list)
class ActionPatch(BaseModel):
    title: str|None = Field(default=None, min_length=2, max_length=300); description: str|None = None; owner_id: str|None = None; due_at: datetime|None = None; sla_minutes: int|None = Field(default=None, ge=1); budget_cents: int|None = Field(default=None, ge=0); stop_conditions: list[str]|None = None
class StepCreate(BaseModel):
    sequence: int = Field(ge=1); channel: str = Field(min_length=2, max_length=40); tool_key: str|None = None; payload: dict = Field(default_factory=dict); requires_approval: bool = False
class ReceiptCreate(BaseModel):
    run_id: str|None = None; step_id: str|None = None; channel: str; external_reference: str = ""; response_code: int|None = None; receipt_payload: dict = Field(default_factory=dict); evidence_content_ids: list[str] = Field(default_factory=list)
class ImpactMetricCreate(BaseModel):
    key: str; name: str; unit: str; direction: str = "higher_is_better"; definition: dict = Field(default_factory=dict)
class ImpactCreate(BaseModel):
    metric_id: str; before_value: float; after_value: float; attribution_confidence: float = Field(ge=0, le=1); attribution_boundary: str = Field(min_length=5); source_content_ids: list[str] = Field(default_factory=list); notes: str = ""
class ReviewCreate(BaseModel):
    outcome: str; failure_mode: str = ""; lessons: str = ""; stop_condition_met: bool = False
class DrillCreate(BaseModel):
    drill_type: str; input_snapshot: dict = Field(default_factory=dict); expected_result: dict = Field(default_factory=dict)
class BenchmarkCreate(BaseModel):
    metric_key: str; cohort: str; sample_size: int = Field(ge=5); aggregate_value: float; k_anonymity: int = Field(default=5, ge=5)
