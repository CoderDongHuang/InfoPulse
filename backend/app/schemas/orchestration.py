"""Agent orchestration request contracts."""
from typing import Literal
from pydantic import BaseModel, Field, field_validator

NodeType=Literal["start","agent","tool","approval","condition","memory_read","memory_write","end"]

class ToolCreate(BaseModel):
    key:str=Field(pattern=r"^[a-z][a-z0-9_.-]{2,79}$");name:str=Field(min_length=2,max_length=120);description:str=Field(default="",max_length=500);input_schema:dict=Field(default_factory=dict);risk_level:Literal["low","medium","high","critical"]="low";connector_key:str|None=None;action:str=Field(min_length=2,max_length=80)
class PolicyUpsert(BaseModel):
    tool_id:str;workspace_id:str|None=None;effect:Literal["allow","deny"]="deny";require_approval:bool=True;max_calls_per_run:int=Field(default=1,ge=1,le=100);constraints:dict=Field(default_factory=dict)
class WorkflowCreate(BaseModel):
    name:str=Field(min_length=2,max_length=160);description:str=Field(default="",max_length=1000);workspace_id:str|None=None;graph:dict;change_note:str=Field(default="Initial version",max_length=500)
class WorkflowVersionCreate(BaseModel): graph:dict;change_note:str=Field(min_length=2,max_length=500)
class RunCreate(BaseModel): input:dict=Field(default_factory=dict);budget_cents:int=Field(default=100,ge=0,le=100000);idempotency_key:str=Field(min_length=8,max_length=100,pattern=r"^[A-Za-z0-9_.:-]+$")
class ApprovalDecision(BaseModel): decision:Literal["approved","rejected"];note:str=Field(min_length=2,max_length=1000)
class PromptCreate(BaseModel): key:str=Field(pattern=r"^[a-z][a-z0-9_.-]{2,79}$");system_prompt:str=Field(min_length=10,max_length=20000);input_variables:list[str]=Field(default_factory=list,max_length=30);status:Literal["draft","active"]="draft"
class RouteUpsert(BaseModel): workspace_id:str|None=None;task_type:str=Field(min_length=2,max_length=60);primary_model:str=Field(min_length=2,max_length=120);fallback_models:list[str]=Field(default_factory=list,max_length=5);max_cost_cents:int=Field(default=100,ge=0,le=100000);max_tokens:int=Field(default=4000,ge=128,le=32000);enabled:bool=True
class MemoryPut(BaseModel): workspace_id:str|None=None;run_id:str|None=None;namespace:str=Field(min_length=2,max_length=80);key:str=Field(min_length=1,max_length=120);value:dict;ttl_seconds:int|None=Field(default=None,ge=60,le=31536000)
class DatasetCreate(BaseModel):
    name:str=Field(min_length=2,max_length=160);cases:list[dict]=Field(min_length=1,max_length=200);thresholds:dict=Field(default_factory=lambda:{"minimum_score":0.8})
    @field_validator("cases")
    @classmethod
    def cases_are_controlled(cls,items):
        allowed={"name","input","expected_status","expected_output_contains","forbidden_tools"}
        if any(not set(x).issubset(allowed) or "name" not in x or "input" not in x for x in items):raise ValueError("evaluation cases contain unsupported fields")
        return items
class TemplateCreate(BaseModel): key:str=Field(pattern=r"^[a-z][a-z0-9_.-]{2,79}$");name:str=Field(min_length=2,max_length=160);category:str=Field(min_length=2,max_length=40);graph:dict;published:bool=False
