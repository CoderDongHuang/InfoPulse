from typing import Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator


Permission = Literal["org.read", "org.manage", "members.manage", "roles.manage", "sso.manage", "approvals.request", "approvals.decide", "audit.export", "legal_hold.manage", "policy.manage", "billing.read", "billing.manage", "sla.read"]


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")
    data_region: Literal["global", "cn", "eu", "us", "apac"] = "global"


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")


class MemberCreate(BaseModel):
    email: str = Field(min_length=3, max_length=100)
    role_key: str = Field(default="member", pattern=r"^[a-z][a-z0-9_.-]{1,39}$")
    workspace_ids: list[str] = Field(default_factory=list, max_length=50)


class RoleCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,39}$")
    name: str = Field(min_length=2, max_length=80)
    permissions: list[Permission] = Field(min_length=1)


class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=500)
    user_ids: list[str] = Field(default_factory=list, max_length=100)


class IdentityProviderCreate(BaseModel):
    provider_type: Literal["oidc", "saml", "scim"]
    name: str = Field(min_length=2, max_length=100)
    issuer: str = Field(default="", max_length=500)
    client_id: str = Field(default="", max_length=200)
    metadata: dict = Field(default_factory=dict)
    enabled: bool = False

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict) -> dict:
        allowed = {"authorization_endpoint", "token_endpoint", "jwks_uri", "sso_url", "entity_id", "signing_certificate", "email_attribute"}
        if set(value) - allowed:
            raise ValueError("identity metadata contains unsupported fields")
        for key, item in value.items():
            if not isinstance(item, str) or len(item) > 8000:
                raise ValueError(f"invalid identity metadata field: {key}")
        return value


class ApprovalCreate(BaseModel):
    workspace_id: str | None = None
    action_type: Literal["bulk_export", "external_webhook", "delete_workspace", "rotate_scim_token", "change_data_region", "raise_model_budget"]
    risk_level: Literal["medium", "high", "critical"] = "high"
    payload: dict = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(min_length=3, max_length=1000)


class PolicyUpdate(BaseModel):
    require_sso: bool = False
    require_mfa: bool = False
    approval_for_high_risk: bool = True
    session_minutes: int = Field(default=480, ge=15, le=1440)
    allowed_email_domains: list[str] = Field(default_factory=list, max_length=50)
    retention_days: int = Field(default=365, ge=30, le=3650)


class QuotaUpdate(BaseModel):
    member_limit: int = Field(ge=1, le=100000)
    storage_bytes: int = Field(ge=1_073_741_824, le=10_995_116_277_760)
    monthly_model_tokens: int = Field(ge=1000, le=10_000_000_000)
    monthly_cost_limit: float = Field(ge=1, le=10_000_000)
    alert_at_percent: int = Field(default=80, ge=50, le=100)


class LegalHoldCreate(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    reason: str = Field(min_length=3, max_length=4000)
    scope: dict = Field(default_factory=dict)


class ScimUserCreate(BaseModel):
    userName: str = Field(min_length=3, max_length=100)
    active: bool = True
    displayName: str = Field(default="", max_length=100)

