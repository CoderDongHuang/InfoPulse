from typing import Literal
from pydantic import BaseModel, Field
AnalysisType=Literal["summary","viewpoints","controversies","causes","impact","risk","forecast","advice","retrospective","propagation","compare"]
class AnalysisRequest(BaseModel):
    analysis_type: AnalysisType
    event_ids: list[str]=Field(default_factory=list,max_length=5)
    content_ids: list[str]=Field(default_factory=list,max_length=50)
    depth: Literal["quick","standard","deep"]="standard"
    language: str="zh-CN"
class RegenerateRequest(BaseModel):
    instruction: str=Field(default="",max_length=1000)
