from typing import Literal
from pydantic import BaseModel,Field
class TranslationRequest(BaseModel):target_language:str=Field(pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")
class NarrativeBuild(BaseModel):event_id:str;workspace_id:str|None=None
class ScenarioCreate(BaseModel):event_id:str;workspace_id:str|None=None;name:str=Field(min_length=2,max_length=300);assumptions:list[str]=Field(min_length=1,max_length=20);evidence_content_ids:list[str]=Field(min_length=2,max_length=50)
class RoomCreate(BaseModel):event_id:str;workspace_id:str|None=None;name:str=Field(min_length=2,max_length=300)
class OptionCreate(BaseModel):title:str=Field(min_length=2,max_length=300);constraints:list[str]=Field(default_factory=list,max_length=20);benefits:list[str]=Field(default_factory=list,max_length=20);side_effects:list[str]=Field(default_factory=list,max_length=20);evidence_content_ids:list[str]=Field(min_length=1,max_length=50)
class FreezeDecision(BaseModel):note:str=Field(min_length=2,max_length=1000)
