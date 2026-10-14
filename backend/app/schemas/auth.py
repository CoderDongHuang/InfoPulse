"""
InfoPulse — Auth Schemas
=========================
Pydantic models for authentication requests/responses.
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pydantic.json_schema import SkipJsonSchema


def normalize_username(value):
    if not isinstance(value, str):
        raise ValueError("用户名必须是字符串")
    value = value.strip()
    if "@" in value:
        raise ValueError("用户名不能包含 @")
    return value


class UserRegisterRequest(BaseModel):
    """Request body for user registration."""
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: EmailStr = Field(..., max_length=100, description="Email address")
    password: str = Field(..., min_length=6, max_length=128, description="Password (min 6 chars)")

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return normalize_username(value)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class UserLoginRequest(BaseModel):
    """Request body for user login."""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")

    @field_validator("username")
    @classmethod
    def normalize_account(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("请输入用户名或邮箱")
        return value


class TokenResponse(BaseModel):
    """Response containing JWT tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user profile returned by the API."""
    id: str
    username: str
    email: str
    avatar_url: str
    is_active: bool
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


def profile_schema(schema):
    # None is an internal sentinel for omission, not an accepted JSON value.
    for field in schema.get("properties", {}).values():
        field.pop("default", None)


class UserUpdateRequest(BaseModel):
    """Omitted fields are unchanged; explicit null is never a stored value."""
    model_config = ConfigDict(json_schema_extra=profile_schema)
    username: str | SkipJsonSchema[None] = Field(None, min_length=3, max_length=50)
    email: EmailStr | SkipJsonSchema[None] = Field(None, max_length=100)
    avatar_url: str | SkipJsonSchema[None] = Field(None, max_length=500)

    @field_validator("username", "email", "avatar_url", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("省略字段以保留原值；清空头像请使用空字符串")
        return value

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value):
        return normalize_username(value)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return str(value).lower()


class AccountDeleteRequest(BaseModel):
    password: str = Field(..., min_length=6, max_length=128)
    confirmation: str = Field(..., pattern="^DELETE$")
