"""Request and response schemas for InfoPulse AI workflows."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


Platform = Literal["weibo", "bilibili", "tieba"]


class InsightRequest(BaseModel):
    keyword: str = Field(min_length=2, max_length=80)
    platforms: list[Platform] = Field(default_factory=lambda: ["weibo", "bilibili", "tieba"], min_length=1)
    max_items: int = Field(default=30, ge=6, le=90)

    @field_validator("platforms")
    @classmethod
    def unique_platforms(cls, value: list[Platform]) -> list[Platform]:
        return list(dict.fromkeys(value))


class MouthpieceRequest(BaseModel):
    source_text: str = Field(min_length=8, max_length=3000)
    scene: Literal["social", "workplace", "review", "announcement"] = "social"
    tone: Literal["sharp", "humorous", "gentle", "rational"] = "humorous"
    intensity: int = Field(default=60, ge=0, le=100)
    length: Literal["short", "medium", "long"] = "medium"


class TimelineRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=100)
    platforms: list[Platform] = Field(default_factory=lambda: ["weibo", "bilibili", "tieba"], min_length=1)
    max_items: int = Field(default=36, ge=6, le=90)

    @field_validator("platforms")
    @classmethod
    def unique_platforms(cls, value: list[Platform]) -> list[Platform]:
        return list(dict.fromkeys(value))


class HotItemRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    platform: str = Field(default="unknown", max_length=30)
    heat: int = Field(default=0, ge=0)
    url: str = Field(default="", max_length=1000)
    category: str = Field(default="热门", max_length=60)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=20)
