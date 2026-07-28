from pydantic import BaseModel,Field
from typing import Literal
ReportType=Literal["daily","weekly","event","industry","executive","risk"]
class ReportCreate(BaseModel):
 title:str=Field(min_length=1,max_length=300);report_type:ReportType;source_config:dict=Field(default_factory=dict);template_id:str|None=None
class RewriteRequest(BaseModel):selected_text:str=Field(min_length=1,max_length=30000);instruction:str=Field(min_length=1,max_length=1000)
class ReportUpdate(BaseModel):title:str|None=None;status:str|None=None
class VersionCreate(BaseModel):content_markdown:str=Field(max_length=200000);structured_content:dict=Field(default_factory=dict);citation_content_ids:list[str]=Field(default_factory=list,max_length=200)
class ExportCreate(BaseModel):format:Literal["docx","pdf","markdown","html"]
