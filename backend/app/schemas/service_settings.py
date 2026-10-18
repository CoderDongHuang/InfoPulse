"""Strict configuration input; secrets are write-only and blank means retain."""
import re
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from app.core.outbound import public_addresses


class ServiceSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=0)
    llm_api_base: str = Field(default="https://api.openai.com/v1", max_length=500)
    llm_model: str = Field(default="gpt-4o-mini", min_length=1, max_length=150)
    llm_api_key: SecretStr = SecretStr("")
    media_vision_model: str = Field(default="", max_length=150)
    media_transcription_model: str = Field(default="", max_length=150)
    smtp_host: str = Field(default="", max_length=253)
    smtp_port: Literal[465, 587] = 587
    smtp_username: str = Field(default="", max_length=254)
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = Field(default="", max_length=254)
    clear_secrets: list[Literal["llm_api_key", "smtp_password"]] = Field(default_factory=list, max_length=2)

    @field_validator("llm_api_key", "smtp_password")
    @classmethod
    def bounded_secret(cls, value):
        raw = value.get_secret_value()
        if len(raw) > 4096 or any(c in raw for c in "\r\n\x00"):
            raise ValueError("Invalid credential format")
        return value

    @field_validator("llm_api_base")
    @classmethod
    def public_https_endpoint(cls, value):
        value = value.strip().rstrip("/")
        try:
            public_addresses(value, https_only=True, resolve_dns=False)
            url = httpx.URL(value)
        except httpx.InvalidURL:
            raise ValueError("Invalid model endpoint URL") from None
        if url.query:
            raise ValueError("Endpoint must not contain query parameters")
        return value

    @field_validator("smtp_host")
    @classmethod
    def public_smtp_host(cls, value):
        value = value.strip().lower()
        if value:
            if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", value):
                raise ValueError("Use a public SMTP hostname")
            public_addresses("https://" + value, https_only=True, resolve_dns=False)
        return value

    @field_validator("smtp_from")
    @classmethod
    def sender_email(cls, value):
        if value:
            from pydantic import TypeAdapter
            return str(TypeAdapter(EmailStr).validate_python(value))
        return value

    @field_validator("llm_model", "media_vision_model", "media_transcription_model", "smtp_username")
    @classmethod
    def no_control_characters(cls, value, info):
        if any(ord(c) < 32 for c in value):
            raise ValueError("Control characters are forbidden")
        value = value.strip()
        if info.field_name == "llm_model" and not value:
            raise ValueError("A text model is required")
        return value
