"""Open platform cryptography, quota, webhook and marketplace helpers."""
import base64
import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform import APIUsageMeter, BillingAccount, ConnectorDefinition, SubscriptionPlan

API_SCOPES = {"events:read", "search:read", "reports:read", "reports:write", "webhooks:read", "webhooks:write", "knowledge:read", "agent:run"}
CONNECTORS = (
    ("slack", "Slack", "collaboration", ["notify", "commands"], ["chat:write"], True),
    ("microsoft_teams", "Microsoft Teams", "collaboration", ["notify", "cards"], ["ChannelMessage.Send"], True),
    ("feishu", "飞书", "collaboration", ["notify", "cards"], ["im:message"], True),
    ("dingtalk", "钉钉", "collaboration", ["notify", "robots"], ["robot:write"], True),
    ("jira", "Jira", "work", ["issues:read", "issues:write"], ["write:jira-work"], True),
    ("notion", "Notion", "knowledge", ["pages:read", "pages:write"], ["insert_content"], True),
    ("confluence", "Confluence", "knowledge", ["pages:read", "pages:write"], ["write:confluence-content"], True),
    ("wecom", "企业微信", "collaboration", ["notify", "contacts:read"], ["message.send"], True),
)


def hash_secret(value: str) -> str: return hashlib.sha256(value.encode()).hexdigest()


def issue_secret(prefix: str) -> tuple[str, str, str]:
    raw = f"{prefix}_{secrets.token_urlsafe(32)}"
    return raw, raw[:12], hash_secret(raw)


def pkce_s256(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def sign_webhook(secret: str, timestamp: str, event_id: str, body: bytes) -> str:
    return hmac.new(secret.encode(), timestamp.encode() + b"." + event_id.encode() + b"." + body, hashlib.sha256).hexdigest()


def verify_webhook(secret: str, timestamp: str, event_id: str, body: bytes, signature: str) -> bool:
    return hmac.compare_digest(sign_webhook(secret, timestamp, event_id, body), signature.removeprefix("sha256="))


def validate_outbound_url(url: str, allow_http_loopback: bool = False) -> None:
    parsed = urlparse(url)
    if parsed.username or parsed.password or not parsed.hostname or parsed.fragment:
        raise HTTPException(422, "Webhook URL is invalid")
    if parsed.scheme != "https" and not (allow_http_loopback and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}):
        raise HTTPException(422, "Webhook URL must use HTTPS")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise HTTPException(422, "Webhook hostname cannot be resolved") from exc
    if any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise HTTPException(422, "Webhook target must resolve only to public addresses")


async def seed_catalog(db: AsyncSession) -> None:
    for key, name, category, capabilities, scopes, write in CONNECTORS:
        if not await db.get(ConnectorDefinition, key):
            db.add(ConnectorDefinition(key=key, name=name, category=category, capabilities=capabilities, required_scopes=scopes, write_capable=write))
    for key, name, limit, overage, cents in (("developer", "Developer", 10_000, False, 0), ("growth", "Growth", 250_000, True, 1), ("enterprise", "Enterprise", 2_000_000, True, 1)):
        if not await db.get(SubscriptionPlan, key):
            db.add(SubscriptionPlan(key=key, name=name, monthly_request_limit=limit, overage_allowed=overage, unit_price_cents=cents))
    await db.flush()


async def enforce_and_meter(db: AsyncSession, organization_id: str, workspace_id: str | None, scope: str, units: int = 1) -> None:
    await seed_catalog(db)
    account = await db.get(BillingAccount, organization_id)
    if not account:
        account = BillingAccount(organization_id=organization_id, plan_key="developer")
        db.add(account); await db.flush()
    plan = await db.get(SubscriptionPlan, account.plan_key)
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    meter = await db.scalar(select(APIUsageMeter).where(APIUsageMeter.organization_id == organization_id, APIUsageMeter.workspace_id == workspace_id, APIUsageMeter.period == period, APIUsageMeter.scope == scope))
    if not meter:
        meter = APIUsageMeter(organization_id=organization_id, workspace_id=workspace_id, period=period, scope=scope)
        db.add(meter); await db.flush()
    total = sum((await db.scalars(select(APIUsageMeter.requests).where(APIUsageMeter.organization_id == organization_id, APIUsageMeter.period == period))).all())
    if total + units > plan.monthly_request_limit and not (plan.overage_allowed and account.overage_enabled):
        raise HTTPException(429, detail={"code": "plan_quota_exceeded", "period": period, "limit": plan.monthly_request_limit})
    meter.requests += units; meter.billable_units += units


def canonical_payload(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
