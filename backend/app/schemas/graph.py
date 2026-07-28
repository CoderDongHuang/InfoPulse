from typing import Literal
from pydantic import BaseModel,Field
EntityType=Literal["person","company","organization","product","project","location","industry","policy","event"]
class GraphBuildRequest(BaseModel):max_nodes:int=Field(default=80,ge=2,le=200)
class EntityCorrection(BaseModel):name:str=Field(min_length=1,max_length=300);entity_type:EntityType;aliases:list[str]=Field(default_factory=list,max_length=30);role:str=Field(default="mentioned",max_length=40);evidence_content_ids:list[str]=Field(default_factory=list,max_length=50)
class EntityMerge(BaseModel):source_entity_id:str;target_entity_id:str
class RelationCreate(BaseModel):from_entity_id:str;to_entity_id:str;relation_type:str=Field(min_length=1,max_length=50);evidence_content_ids:list[str]=Field(min_length=1,max_length=50);confidence:float=Field(default=1,ge=0,le=1)
class EdgeCorrection(BaseModel):relation_type:Literal["reference","repost","similar","inferred"]|None=None;confidence:float|None=Field(default=None,ge=0,le=1);is_verified:bool|None=None
