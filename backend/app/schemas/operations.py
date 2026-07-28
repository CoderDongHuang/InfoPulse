from typing import Literal
from pydantic import BaseModel,Field,field_validator

class ProductEventCreate(BaseModel):
    event_name:Literal["page_view","search_completed","event_opened","analysis_saved","report_exported","alert_resolved","help_opened"]
    route:str=Field(max_length=120,pattern=r"^/[A-Za-z0-9_./:-]*$")
    properties:dict[str,str|int|bool]=Field(default_factory=dict)
    @field_validator("properties")
    @classmethod
    def controlled_properties(cls,value):
        allowed={"source","format","status","category","result_count","duration_bucket"}
        if set(value)-allowed:raise ValueError("unsupported analytics property")
        if any(isinstance(item,str) and len(item)>100 for item in value.values()):raise ValueError("analytics property is too long")
        return value

class FeedbackCreate(BaseModel):
    category:Literal["bug","idea","data_quality","ai_quality","other"]
    rating:int=Field(ge=1,le=5)
    message:str=Field(min_length=3,max_length=2000)

class FeedbackUpdate(BaseModel):status:Literal["new","reviewing","planned","resolved","closed"]

class ReleaseCreate(BaseModel):
    version:str=Field(min_length=1,max_length=80,pattern=r"^[A-Za-z0-9._-]+$")
    environment:Literal["staging","production"]
    status:Literal["deploying","canary","succeeded","rolled_back","failed"]
    commit_sha:str=Field(min_length=7,max_length=64,pattern=r"^[a-fA-F0-9]+$")
    notes:str=Field(default="",max_length=4000)
    metrics:dict=Field(default_factory=dict)
