from pydantic import BaseModel,Field
from typing import Literal
class ConversationCreate(BaseModel):
 title:str=Field(default="新会话",max_length=200);event_id:str|None=None;context_config:dict=Field(default_factory=dict)
class ConversationUpdate(BaseModel): title:str|None=Field(default=None,max_length=200);context_config:dict|None=None
class MessageCreate(BaseModel):
 content:str=Field(min_length=1,max_length=8000);context_additions:list[dict]=Field(default_factory=list,max_length=20);knowledge_base_ids:list[str]=Field(default_factory=list,max_length=10)
class FeedbackCreate(BaseModel): rating:Literal["up","down"];reason:str=Field(default="",max_length=500)
