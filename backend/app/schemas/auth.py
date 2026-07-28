"""
InfoPulse — Auth Schemas
=========================
Pydantic models for authentication requests/responses.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    """Request body for user registration."""
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: EmailStr = Field(..., max_length=100, description="Email address")
    password: str = Field(..., min_length=6, max_length=128, description="Password (min 6 chars)")

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("用户名不能为空")
        if "@" in value:
            raise ValueError("用户名不能包含 @")
        return value

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
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    """Request body for updating user profile."""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=500)
