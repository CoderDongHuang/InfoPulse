from typing import Literal
from pydantic import BaseModel,Field,field_validator
class CitationCreate(BaseModel):target_type:Literal["report","workflow","analysis","agent_message"];target_id:str;claim_index:int=Field(default=0,ge=0);quote:str=Field(min_length=1,max_length=1000)
class LiveCreate(BaseModel):name:str=Field(min_length=2,max_length=160);workspace_id:str|None=None;source_type:Literal["field","hls","rtmp","webinar"]="field";source_url:str=Field(default="",max_length=1000)
class LiveUpdateCreate(BaseModel):update_type:Literal["observation","transcript","risk","location","media","status"];payload:dict;asset_id:str|None=None;occurred_at:str|None=None
class CollabOpen(BaseModel):resource_type:Literal["report","workflow"];resource_id:str;workspace_id:str|None=None
class ChangeCreate(BaseModel):
 base_version:int=Field(ge=1);client_id:str=Field(min_length=8,max_length=80,pattern=r"^[A-Za-z0-9_.:-]+$");client_sequence:int=Field(ge=1);operations:list[dict]=Field(min_length=1,max_length=100)
 @field_validator("operations")
 @classmethod
 def controlled(cls,ops):
  for op in ops:
   if set(op)-{"op","path","value"} or op.get("op") not in {"set","remove"} or not isinstance(op.get("path"),str):raise ValueError("only controlled set/remove operations are supported")
   parts=[x for x in op["path"].strip("/").split("/") if x]
   if not 1<=len(parts)<=4 or any(x in {"__proto__","prototype","constructor"} or not x.replace("_","").isalnum() for x in parts):raise ValueError("invalid change path")
  return ops
class ConflictResolve(BaseModel):strategy:Literal["keep_server","apply_client"];operations:list[dict]=Field(default_factory=list,max_length=100)
class CommentCreate(BaseModel):body:str=Field(min_length=1,max_length=5000);anchor:dict=Field(default_factory=dict);parent_id:str|None=None;mention_user_ids:list[str]=Field(default_factory=list,max_length=30)
class SafetyDecision(BaseModel):decision:Literal["approved","restricted","rejected"];note:str=Field(min_length=2,max_length=1000)
