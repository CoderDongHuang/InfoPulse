from typing import Literal
from pydantic import BaseModel, Field
class TargetRequest(BaseModel):
    target_type: Literal["content", "event", "report"]
    target_id: str
    title: str = ""
class TopicRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    keywords: list[str] = Field(default_factory=list)
    enabled: bool = True
class FeedbackRequest(BaseModel):
    feedback_type: Literal["not_interested", "seen", "low_quality", "irrelevant"]
    reason: str = Field(default="", max_length=500)
