from typing import Literal

from pydantic import BaseModel, Field, field_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TaskType = Literal["daily_report", "keyword_monitor", "company_monitor"]


class SubscriptionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    target_type: Literal["keyword", "company", "industry", "search", "report"]
    target_id: str | None = None
    query: str = Field(default="", max_length=500)
    filters: dict = Field(default_factory=dict)
    schedule: dict = Field(default_factory=lambda: {"kind": "daily", "time": "09:00"})
    timezone: str = "Asia/Shanghai"
    channels: list[Literal["in_app", "email", "webhook"]] = Field(default_factory=lambda: ["in_app"])
    enabled: bool = True

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try: ZoneInfo(value)
        except ZoneInfoNotFoundError as exc: raise ValueError("Invalid IANA timezone") from exc
        return value


class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    task_type: TaskType
    config: dict = Field(default_factory=dict)
    schedule: dict = Field(default_factory=lambda: {"kind": "daily", "time": "09:00"})
    timezone: str = "Asia/Shanghai"
    max_retries: int = Field(default=3, ge=0, le=10)
    max_concurrency: int = Field(default=1, ge=1, le=10)
    cost_limit: float = Field(default=1.0, ge=0, le=1000)
    estimated_cost: float = Field(default=0, ge=0, le=1000)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try: ZoneInfo(value)
        except ZoneInfoNotFoundError as exc: raise ValueError("Invalid IANA timezone") from exc
        return value


class NotificationPreferenceUpdate(BaseModel):
    timezone: str = "Asia/Shanghai"
    quiet_hours_enabled: bool = False
    quiet_start: str = Field(default="22:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    quiet_end: str = Field(default="08:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    digest_enabled: bool = True
    email_enabled: bool = False
    email_address: str = Field(default="", max_length=320)
    webhook_enabled: bool = False
    webhook_url: str = Field(default="", max_length=1000)
    webhook_secret: str = Field(default="", max_length=300)

