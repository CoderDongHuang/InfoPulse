"""Tenant open platform: credentials, OAuth 2.1, webhooks, integrations and metering."""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import get_db
from app.dependencies import get_current_user, get_tenant_context
from app.models.intelligence import AuditLog
from app.models.platform import APIUsageMeter, BillingAccount, ConnectorDefinition, ConnectorInstallation, DeveloperAPIKey, OAuthAccessGrant, OAuthApplication, OAuthAuthorizationCode, SecurityReview, SubscriptionPlan, WebhookDelivery, WebhookEndpoint
from app.models.user import User
from app.schemas.platform import APIKeyCreate, ConnectorInstall, OAuthAppCreate, OAuthAuthorize, OAuthTokenExchange, ReviewDecision, SandboxRequest, WebhookCreate, WebhookTest
from app.services.enterprise import TenantContext, require_permission, set_db_context
from app.services.platform import canonical_payload, enforce_and_meter, hash_secret, issue_secret, pkce_s256, seed_catalog, sign_webhook, validate_outbound_url

router = APIRouter(prefix="/api/v1/platform", tags=["Open Platform"])
optional_bearer = HTTPBearer(auto_error=False)


def audit(db, user, org, action, target, target_id, after=None):
    db.add(AuditLog(user_id=user.id, organization_id=org, action=action, target_type=target, target_id=target_id, after_data=after or {}))


def cipher() -> Fernet:
    raw = get_settings().PLATFORM_ENCRYPTION_KEY or get_settings().JWT_SECRET_KEY
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest()))


def key_view(row):
    return {"id": row.id, "name": row.name, "prefix": row.key_prefix, "scopes": row.scopes, "workspace_id": row.workspace_id, "expires_at": row.expires_at, "last_used_at": row.last_used_at, "revoked_at": row.revoked_at, "created_at": row.created_at}


@router.get("/overview")
async def overview(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "developer.read"); await seed_catalog(db)
    counts = {}
    for name, model in (("api_keys", DeveloperAPIKey), ("oauth_apps", OAuthApplication), ("webhooks", WebhookEndpoint), ("installations", ConnectorInstallation)):
        counts[name] = int(await db.scalar(select(func.count()).select_from(model).where(model.organization_id == ctx.organization.id)) or 0)
    return {**counts, "sandbox": {"external_delivery": False, "private_knowledge": False}, "openapi_url": "/openapi.json", "sdk_languages": ["python", "typescript"]}


@router.get("/api-keys")
async def list_keys(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "developer.read")
    return [key_view(x) for x in (await db.scalars(select(DeveloperAPIKey).where(DeveloperAPIKey.organization_id == ctx.organization.id).order_by(DeveloperAPIKey.created_at.desc()))).all()]


@router.post("/api-keys", status_code=201)
async def create_key(payload: APIKeyCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "developer.manage")
    if payload.workspace_id and (not ctx.workspace or ctx.workspace.id != payload.workspace_id): raise HTTPException(403, "Select the target workspace in tenant context")
    raw, prefix, digest = issue_secret("ipk_live")
    row = DeveloperAPIKey(organization_id=ctx.organization.id, workspace_id=payload.workspace_id, name=payload.name, key_prefix=prefix, key_hash=digest, scopes=sorted(set(payload.scopes)), created_by=user.id, expires_at=payload.expires_at)
    db.add(row); await db.flush(); audit(db, user, ctx.organization.id, "api_key.create", "api_key", row.id, {"prefix": prefix, "scopes": row.scopes})
    return {**key_view(row), "secret": raw, "secret_notice": "This value is shown once and cannot be recovered."}


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_key(key_id: str, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "developer.manage"); row = await db.get(DeveloperAPIKey, key_id)
    if not row or row.organization_id != ctx.organization.id: raise HTTPException(404, "API key not found")
    row.revoked_at = datetime.now(timezone.utc); audit(db, user, ctx.organization.id, "api_key.revoke", "api_key", row.id)


@router.get("/api-key/whoami")
async def api_key_identity(credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer), required_scope: str = Header("events:read", alias="X-Required-Scope"), db: AsyncSession = Depends(get_db)):
    if not credentials or not credentials.credentials.startswith("ipk_live_"): raise HTTPException(401, "Developer API key required")
    row = await db.scalar(select(DeveloperAPIKey).where(DeveloperAPIKey.key_hash == hash_secret(credentials.credentials)))
    now = datetime.now(timezone.utc)
    if not row or row.revoked_at or (row.expires_at and row.expires_at <= now): raise HTTPException(401, "API key is invalid or expired")
    if required_scope not in row.scopes: raise HTTPException(403, f"Missing scope: {required_scope}")
    await set_db_context(db, row.created_by, row.organization_id); await enforce_and_meter(db, row.organization_id, row.workspace_id, required_scope)
    row.last_used_at = now
    return {"organization_id": row.organization_id, "workspace_id": row.workspace_id, "scopes": row.scopes}


@router.get("/oauth/apps")
async def oauth_apps(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "developer.read")
    rows = (await db.scalars(select(OAuthApplication).where(OAuthApplication.organization_id == ctx.organization.id))).all()
    return [{"id": x.id, "name": x.name, "client_id": x.client_id, "app_type": x.app_type, "redirect_uris": x.redirect_uris, "scopes": x.scopes, "review_status": x.review_status, "revoked_at": x.revoked_at} for x in rows]


@router.post("/oauth/apps", status_code=201)
async def create_oauth_app(payload: OAuthAppCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "developer.manage"); client_id = "ipc_" + secrets.token_urlsafe(20); client_secret = None
    if payload.app_type == "confidential": client_secret, _, secret_hash = issue_secret("ips")
    else: secret_hash = ""
    row = OAuthApplication(organization_id=ctx.organization.id, name=payload.name, client_id=client_id, client_secret_hash=secret_hash, app_type=payload.app_type, redirect_uris=payload.redirect_uris, scopes=sorted(set(payload.scopes)), created_by=user.id)
    db.add(row); await db.flush(); db.add(SecurityReview(organization_id=ctx.organization.id, target_type="oauth_app", target_id=row.id)); audit(db, user, ctx.organization.id, "oauth_app.create", "oauth_app", row.id)
    return {"id": row.id, "client_id": client_id, "client_secret": client_secret, "review_status": row.review_status, "pkce_required": True}


@router.post("/oauth/authorize")
async def authorize(payload: OAuthAuthorize, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    app = await db.scalar(select(OAuthApplication).where(OAuthApplication.client_id == payload.client_id))
    if not app or app.revoked_at or app.review_status != "approved": raise HTTPException(403, "Application is not approved")
    if payload.redirect_uri not in app.redirect_uris or not set(payload.scopes).issubset(app.scopes): raise HTTPException(400, "Redirect URI or scope mismatch")
    ctx = await __import__("app.services.enterprise", fromlist=["resolve_tenant"]).resolve_tenant(db, user, app.organization_id, None)
    code, _, digest = issue_secret("ipc_code")
    db.add(OAuthAuthorizationCode(application_id=app.id, organization_id=ctx.organization.id, user_id=user.id, code_hash=digest, redirect_uri=payload.redirect_uri, scopes=payload.scopes, code_challenge=payload.code_challenge, expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)))
    return {"code": code, "redirect_uri": payload.redirect_uri, "expires_in": 300}


@router.post("/oauth/token")
async def exchange_token(payload: OAuthTokenExchange, db: AsyncSession = Depends(get_db)):
    app = await db.scalar(select(OAuthApplication).where(OAuthApplication.client_id == payload.client_id))
    code = await db.scalar(select(OAuthAuthorizationCode).where(OAuthAuthorizationCode.code_hash == hash_secret(payload.code)))
    now = datetime.now(timezone.utc)
    if not app or not code or code.application_id != app.id or code.consumed_at or code.expires_at <= now or code.redirect_uri != payload.redirect_uri: raise HTTPException(400, "Invalid authorization code")
    if app.app_type == "confidential" and (not payload.client_secret or hash_secret(payload.client_secret) != app.client_secret_hash): raise HTTPException(401, "Invalid client authentication")
    if pkce_s256(payload.code_verifier) != code.code_challenge: raise HTTPException(400, "PKCE verification failed")
    access, _, access_hash = issue_secret("ipa"); refresh, _, refresh_hash = issue_secret("ipr"); code.consumed_at = now
    db.add(OAuthAccessGrant(application_id=app.id, organization_id=app.organization_id, user_id=code.user_id, access_token_hash=access_hash, refresh_token_hash=refresh_hash, scopes=code.scopes, expires_at=now + timedelta(hours=1)))
    return {"access_token": access, "refresh_token": refresh, "token_type": "Bearer", "expires_in": 3600, "scope": " ".join(code.scopes)}


@router.post("/oauth/apps/{app_id}/review")
async def review_app(app_id: str, payload: ReviewDecision, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "integrations.approve"); app = await db.get(OAuthApplication, app_id)
    if not app or app.organization_id != ctx.organization.id: raise HTTPException(404, "Application not found")
    review = await db.scalar(select(SecurityReview).where(SecurityReview.organization_id == ctx.organization.id, SecurityReview.target_type == "oauth_app", SecurityReview.target_id == app.id))
    app.review_status = payload.decision; review.status = payload.decision; review.findings = payload.findings; review.reviewed_by = user.id; review.reviewed_at = datetime.now(timezone.utc)
    audit(db, user, ctx.organization.id, "oauth_app.review", "oauth_app", app.id, {"decision": payload.decision})


@router.delete("/oauth/apps/{app_id}", status_code=204)
async def revoke_app(app_id: str, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "developer.manage"); app = await db.get(OAuthApplication, app_id)
    if not app or app.organization_id != ctx.organization.id: raise HTTPException(404, "Application not found")
    app.revoked_at = datetime.now(timezone.utc)
    grants = (await db.scalars(select(OAuthAccessGrant).where(OAuthAccessGrant.application_id == app.id, OAuthAccessGrant.revoked_at.is_(None)))).all()
    for grant in grants: grant.revoked_at = app.revoked_at
    audit(db, user, ctx.organization.id, "oauth_app.revoke", "oauth_app", app.id)


@router.get("/webhooks")
async def webhooks(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "developer.read"); rows = (await db.scalars(select(WebhookEndpoint).where(WebhookEndpoint.organization_id == ctx.organization.id))).all()
    return [{"id": x.id, "name": x.name, "target_url": x.target_url, "event_types": x.event_types, "enabled": x.enabled, "revoked_at": x.revoked_at} for x in rows]


@router.post("/webhooks", status_code=201)
async def create_webhook(payload: WebhookCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "developer.manage"); validate_outbound_url(payload.target_url)
    secret, _, digest = issue_secret("whsec")
    row = WebhookEndpoint(organization_id=ctx.organization.id, workspace_id=payload.workspace_id, name=payload.name, target_url=payload.target_url, event_types=sorted(set(payload.event_types)), secret_hash=digest, secret_ciphertext=cipher().encrypt(secret.encode()).decode())
    db.add(row); await db.flush(); audit(db, user, ctx.organization.id, "webhook.create", "webhook", row.id)
    return {"id": row.id, "secret": secret, "secret_notice": "This signing secret is shown once."}


@router.post("/webhooks/{endpoint_id}/test")
async def test_webhook(endpoint_id: str, payload: WebhookTest, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "developer.manage"); endpoint = await db.get(WebhookEndpoint, endpoint_id)
    if not endpoint or endpoint.organization_id != ctx.organization.id or endpoint.revoked_at: raise HTTPException(404, "Webhook not found")
    event_id = "evt_" + secrets.token_urlsafe(12); body = {"id": event_id, "type": payload.event_type, "sandbox": True, "data": {}}
    raw = canonical_payload(body); timestamp = str(int(datetime.now(timezone.utc).timestamp())); secret = cipher().decrypt(endpoint.secret_ciphertext.encode()).decode()
    fingerprint = hashlib.sha256(endpoint.id.encode() + raw).hexdigest()
    row = WebhookDelivery(organization_id=ctx.organization.id, endpoint_id=endpoint.id, event_id=event_id, event_type=payload.event_type, fingerprint=fingerprint, payload=body, status="sandboxed")
    db.add(row); await db.flush()
    return {"delivery_id": row.id, "sent": False, "headers": {"InfoPulse-Event-ID": event_id, "InfoPulse-Timestamp": timestamp, "InfoPulse-Signature": "sha256=" + sign_webhook(secret, timestamp, event_id, raw)}, "body": body}


@router.get("/webhooks/deliveries")
async def deliveries(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "developer.read"); rows = (await db.scalars(select(WebhookDelivery).where(WebhookDelivery.organization_id == ctx.organization.id).order_by(WebhookDelivery.created_at.desc()).limit(100))).all()
    return [{"id": x.id, "endpoint_id": x.endpoint_id, "event_id": x.event_id, "event_type": x.event_type, "attempt": x.attempt, "status": x.status, "response_code": x.response_code, "error": x.error, "replay_of_id": x.replay_of_id, "created_at": x.created_at} for x in rows]


@router.post("/webhooks/deliveries/{delivery_id}/replay", status_code=201)
async def replay(delivery_id: str, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "developer.manage"); old = await db.get(WebhookDelivery, delivery_id)
    if not old or old.organization_id != ctx.organization.id: raise HTTPException(404, "Delivery not found")
    attempt = int(await db.scalar(select(func.max(WebhookDelivery.attempt)).where(WebhookDelivery.endpoint_id == old.endpoint_id, WebhookDelivery.fingerprint == old.fingerprint)) or 0) + 1
    row = WebhookDelivery(organization_id=old.organization_id, endpoint_id=old.endpoint_id, event_id=old.event_id, event_type=old.event_type, fingerprint=old.fingerprint, payload=old.payload, attempt=attempt, status="queued", replay_of_id=old.id)
    db.add(row); await db.flush(); return {"id": row.id, "status": row.status, "attempt": row.attempt, "replay_of_id": old.id}


@router.get("/marketplace")
async def marketplace(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "developer.read"); await seed_catalog(db)
    rows = (await db.scalars(select(ConnectorDefinition).where(ConnectorDefinition.enabled.is_(True)).order_by(ConnectorDefinition.category, ConnectorDefinition.name))).all()
    return [{"key": x.key, "name": x.name, "category": x.category, "capabilities": x.capabilities, "required_scopes": x.required_scopes, "write_capable": x.write_capable} for x in rows]


@router.get("/installations")
async def installations(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "developer.read"); rows = (await db.scalars(select(ConnectorInstallation).where(ConnectorInstallation.organization_id == ctx.organization.id))).all()
    return [{"id": x.id, "connector_key": x.connector_key, "workspace_id": x.workspace_id, "status": x.status, "credential_reference": x.credential_reference.split("/")[0] + "//***", "config": x.config, "revoked_at": x.revoked_at} for x in rows]


@router.post("/installations", status_code=201)
async def install(payload: ConnectorInstall, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "integrations.install"); await seed_catalog(db); definition = await db.get(ConnectorDefinition, payload.connector_key)
    row = ConnectorInstallation(organization_id=ctx.organization.id, workspace_id=payload.workspace_id, connector_key=payload.connector_key, credential_reference=payload.credential_reference, config=payload.config, requested_by=user.id, status="pending" if definition.write_capable else "approved")
    db.add(row); await db.flush(); db.add(SecurityReview(organization_id=ctx.organization.id, target_type="connector", target_id=row.id)); audit(db, user, ctx.organization.id, "connector.install.request", "connector_installation", row.id)
    return {"id": row.id, "status": row.status, "approval_required": definition.write_capable}


@router.post("/installations/{installation_id}/review")
async def review_installation(installation_id: str, payload: ReviewDecision, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "integrations.approve"); row = await db.get(ConnectorInstallation, installation_id)
    if not row or row.organization_id != ctx.organization.id: raise HTTPException(404, "Installation not found")
    row.status = payload.decision; row.approved_by = user.id if payload.decision == "approved" else None
    review = await db.scalar(select(SecurityReview).where(SecurityReview.target_type == "connector", SecurityReview.target_id == row.id, SecurityReview.organization_id == ctx.organization.id)); review.status = payload.decision; review.findings = payload.findings; review.reviewed_by = user.id; review.reviewed_at = datetime.now(timezone.utc)
    audit(db, user, ctx.organization.id, "connector.install.review", "connector_installation", row.id, {"decision": payload.decision})


@router.delete("/installations/{installation_id}", status_code=204)
async def revoke_installation(installation_id: str, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "integrations.install"); row = await db.get(ConnectorInstallation, installation_id)
    if not row or row.organization_id != ctx.organization.id: raise HTTPException(404, "Installation not found")
    row.status = "revoked"; row.revoked_at = datetime.now(timezone.utc); row.credential_reference = ""; audit(db, user, ctx.organization.id, "connector.revoke", "connector_installation", row.id)


@router.get("/usage")
async def usage(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "billing.read"); await seed_catalog(db); account = await db.get(BillingAccount, ctx.organization.id)
    if not account: account = BillingAccount(organization_id=ctx.organization.id, plan_key="developer"); db.add(account); await db.flush()
    plan = await db.get(SubscriptionPlan, account.plan_key); period = datetime.now(timezone.utc).strftime("%Y-%m")
    meters = (await db.scalars(select(APIUsageMeter).where(APIUsageMeter.organization_id == ctx.organization.id, APIUsageMeter.period == period))).all(); used = sum(x.requests for x in meters)
    return {"period": period, "plan": {"key": plan.key, "name": plan.name, "limit": plan.monthly_request_limit, "overage_allowed": plan.overage_allowed}, "used": used, "remaining": max(0, plan.monthly_request_limit - used), "overage_enabled": account.overage_enabled, "by_scope": [{"scope": x.scope, "requests": x.requests} for x in meters]}


@router.post("/sandbox")
async def sandbox(payload: SandboxRequest, ctx: TenantContext = Depends(get_tenant_context)):
    require_permission(ctx, "developer.read")
    safe_input = {k: v for k, v in payload.input.items() if k in {"query", "limit", "event_type"}}
    return {"sandbox": True, "operation": payload.operation, "input": safe_input, "result": [], "constraints": {"external_delivery": False, "private_knowledge": False, "production_mutations": False}}
