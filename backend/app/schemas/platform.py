"""Validated open-platform request contracts."""
from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

Scope = Literal["events:read", "search:read", "reports:read", "reports:write", "webhooks:read", "webhooks:write", "knowledge:read", "agent:run"]
EventType = Literal["event.created", "event.risk_changed", "report.ready", "alert.triggered", "task.failed"]


class APIKeyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scopes: list[Scope] = Field(min_length=1)
    workspace_id: str | None = None
    expires_at: datetime | None = None


class OAuthAppCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    app_type: Literal["public", "confidential"] = "public"
    redirect_uris: list[str] = Field(min_length=1, max_length=10)
    scopes: list[Scope] = Field(min_length=1)

    @field_validator("redirect_uris")
    @classmethod
    def redirects(cls, values: list[str]) -> list[str]:
        for value in values:
            parsed = urlparse(value)
            if parsed.fragment or parsed.username or parsed.password or parsed.scheme not in {"https", "http"}:
                raise ValueError("invalid redirect URI")
            if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost"}:
                raise ValueError("redirect URI must use HTTPS except loopback development")
        return list(dict.fromkeys(values))


class OAuthAuthorize(BaseModel):
    client_id: str
    redirect_uri: str
    scopes: list[Scope] = Field(min_length=1)
    code_challenge: str = Field(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    code_challenge_method: Literal["S256"]


class OAuthTokenExchange(BaseModel):
    grant_type: Literal["authorization_code"]
    client_id: str
    client_secret: str | None = None
    code: str
    redirect_uri: str
    code_verifier: str = Field(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9._~-]+$")


class WebhookCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    target_url: str = Field(max_length=1000)
    event_types: list[EventType] = Field(min_length=1)
    workspace_id: str | None = None


class WebhookTest(BaseModel):
    event_type: EventType = "event.created"


class ConnectorInstall(BaseModel):
    connector_key: Literal["slack", "microsoft_teams", "feishu", "dingtalk", "jira", "notion", "confluence", "wecom"]
    workspace_id: str | None = None
    credential_reference: str = Field(min_length=5, max_length=500, pattern=r"^(vault|aws-secretsmanager|azure-keyvault|gcp-secretmanager)://")
    config: dict = Field(default_factory=dict)


class ReviewDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    findings: list[str] = Field(default_factory=list, max_length=20)


class SandboxRequest(BaseModel):
    operation: Literal["list_events", "search", "render_webhook"]
    input: dict = Field(default_factory=dict)
