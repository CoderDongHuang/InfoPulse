"""Shared response contracts for all v1 APIs."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    has_more: bool


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict | list | None = None
    diagnostic_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody
