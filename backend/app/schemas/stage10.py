from datetime import datetime
from typing import Literal
from pydantic import BaseModel,Field
RuleType=Literal["keyword","heat","negative","media","official","velocity","ai_risk","composite"]
class RuleCreate(BaseModel):name:str=Field(min_length=1,max_length=200);rule_type:RuleType;config:dict=Field(default_factory=dict);combinator:Literal["all","any"]="all";severity:Literal["info","warning","critical"]="warning";assignee_id:str|None=None;enabled:bool=True
class RuleUpdate(BaseModel):name:str|None=Field(default=None,min_length=1,max_length=200);config:dict|None=None;combinator:Literal["all","any"]|None=None;severity:Literal["info","warning","critical"]|None=None;assignee_id:str|None=None;enabled:bool|None=None
class ReplayRequest(BaseModel):from_at:datetime;to_at:datetime
class IncidentActionRequest(BaseModel):action:Literal["assign","acknowledge","resolve","close","reopen","false_positive"];assignee_id:str|None=None;note:str=Field(default="",max_length=2000)
class BIQuestion(BaseModel):question:str=Field(min_length=2,max_length=1000)
