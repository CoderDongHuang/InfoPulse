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
from sqlalchemy import select, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform import APIUsageMeter, BillingAccount, ConnectorDefinition, SubscriptionPlan
from app.core.outbound import public_addresses
from cryptography.fernet import Fernet
from app.config import get_settings

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


def cipher() -> Fernet:
    raw = get_settings().PLATFORM_ENCRYPTION_KEY or get_settings().JWT_SECRET_KEY
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest()))


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
    try:
        public_addresses(url,https_only=True)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc


async def seed_catalog(db: AsyncSession) -> None:
    if db.bind.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        from sqlalchemy.dialects.postgresql import insert
    # Concurrent first visits must not race between a SELECT and an INSERT.
    connectors = [dict(key=key, name=name, category=category, capabilities=capabilities,
                       required_scopes=scopes, write_capable=write)
                  for key, name, category, capabilities, scopes, write in CONNECTORS]
    await db.execute(insert(ConnectorDefinition).values(connectors).on_conflict_do_nothing(index_elements=["key"]))
    plans = [dict(key=key, name=name, monthly_request_limit=limit, overage_allowed=overage, unit_price_cents=cents)
             for key, name, limit, overage, cents in (("developer", "Developer", 10_000, False, 0), ("growth", "Growth", 250_000, True, 1), ("enterprise", "Enterprise", 2_000_000, True, 1))]
    await db.execute(insert(SubscriptionPlan).values(plans).on_conflict_do_nothing(index_elements=["key"]))


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


async def process_webhook_once(sessions=None, client=None) -> bool:
    """Claim before POST; an ambiguous result never triggers automatic resend."""
    import httpx
    from datetime import timedelta
    from app.core.database import _get_sessionmaker
    from app.core.outbound import public_request
    from app.models.platform import WebhookDelivery, WebhookEndpoint
    sessions = sessions or _get_sessionmaker()
    at = datetime.now(timezone.utc)
    async with sessions() as db:
        await db.execute(update(WebhookDelivery).where(WebhookDelivery.status == "running",
            WebhookDelivery.next_attempt_at < at).values(status="unknown", error="Delivery lease expired; reconcile before replay", next_attempt_at=None))
        row = await db.scalar(select(WebhookDelivery).where(WebhookDelivery.status == "queued",
            or_(WebhookDelivery.next_attempt_at.is_(None), WebhookDelivery.next_attempt_at <= at)).order_by(WebhookDelivery.created_at).limit(1))
        if not row:
            await db.commit()
            return False
        claimed = await db.execute(update(WebhookDelivery).where(WebhookDelivery.id == row.id,
            WebhookDelivery.status == "queued").values(status="running", next_attempt_at=at + timedelta(minutes=2)))
        if claimed.rowcount != 1:
            await db.rollback()
            return False
        await db.refresh(row)
        await db.commit()
        endpoint = await db.get(WebhookEndpoint, row.endpoint_id)
        try:
            if not endpoint or endpoint.organization_id != row.organization_id or endpoint.revoked_at or not endpoint.enabled:
                raise ValueError("Webhook endpoint disabled or revoked")
            if row.event_type not in endpoint.event_types:
                raise ValueError("Event type not subscribed")
            raw = canonical_payload(row.payload)
            secret = cipher().decrypt(endpoint.secret_ciphertext.encode()).decode()
            timestamp = str(int(at.timestamp()))
            response = await public_request("POST", endpoint.target_url, client=client,
                https_only=True, max_bytes=64000, max_redirects=0,
                timeout=get_settings().WEBHOOK_TIMEOUT_SECONDS, content=raw, headers={
                    "Content-Type": "application/json", "InfoPulse-Event-ID": row.event_id,
                    "InfoPulse-Timestamp": timestamp,
                    "InfoPulse-Signature": "sha256=" + sign_webhook(secret, timestamp, row.event_id, raw)})
            row.response_code = response.status_code
            row.status = "delivered" if 200 <= response.status_code < 300 else "failed"
            if row.status == "delivered": row.delivered_at = datetime.now(timezone.utc)
            else: row.error = f"Remote endpoint returned HTTP {response.status_code}"
        except (httpx.HTTPError, TimeoutError) as exc:
            row.status = "unknown"; row.error = type(exc).__name__
        except Exception as exc:
            row.status = "failed"; row.error = type(exc).__name__
        row.next_attempt_at = None
        await db.commit()
        return True
