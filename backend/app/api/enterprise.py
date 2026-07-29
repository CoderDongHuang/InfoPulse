"""Enterprise tenancy and governance API."""
from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user, get_tenant_context
from app.models.enterprise import ApprovalRequest, CustomRole, IdentityProvider, LegalHold, Organization, OrganizationMember, Team, TeamMember, TenantPolicy, TenantQuota, TenantSLA, Workspace, WorkspaceMember
from app.models.intelligence import AuditLog, KnowledgeDocument, ModelUsage
from app.models.user import User
from app.schemas.enterprise import ApprovalCreate, ApprovalDecision, IdentityProviderCreate, LegalHoldCreate, MemberCreate, OrganizationCreate, PolicyUpdate, QuotaUpdate, RoleCreate, ScimUserCreate, TeamCreate, WorkspaceCreate
from app.services.enterprise import TenantContext, hash_scim_token, new_scim_token, require_permission, set_db_context
from app.core.security import hash_password
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/api/v1/enterprise", tags=["Enterprise Governance"])
scim_router = APIRouter(prefix="/api/v1/scim/v2", tags=["SCIM 2.0"])
scim_bearer = HTTPBearer()
SECRET = re.compile(r"(?i)(password|secret|token|cookie|authorization|api[_-]?key)")


def clean_payload(value: dict) -> dict:
    if any(SECRET.search(str(key)) for key in value):
        raise HTTPException(422, "Governance payload must not contain credentials")
    rendered = str(value)
    if len(rendered) > 8000:
        raise HTTPException(422, "Governance payload is too large")
    return value


def audit(db: AsyncSession, user: User, action: str, target_type: str, target_id: str, before: dict | None = None, after: dict | None = None, organization_id: str | None = None):
    db.add(AuditLog(user_id=user.id, organization_id=organization_id, action=action, target_type=target_type, target_id=target_id, before_data=before or {}, after_data=after or {}))


@router.get("/context")
async def context(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    workspaces = (await db.scalars(select(Workspace).join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id).where(WorkspaceMember.user_id == ctx.membership.user_id, Workspace.organization_id == ctx.organization.id))).all()
    return {"organization": {"id": ctx.organization.id, "name": ctx.organization.name, "slug": ctx.organization.slug, "data_region": ctx.organization.data_region}, "membership": {"role_key": ctx.membership.role_key}, "permissions": sorted(ctx.permissions), "workspaces": [{"id": x.id, "name": x.name, "slug": x.slug, "status": x.status} for x in workspaces]}


@router.post("/organizations", status_code=201)
async def create_organization(payload: OrganizationCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if await db.scalar(select(Organization.id).where(Organization.slug == payload.slug)):
        raise HTTPException(409, "Organization slug already exists")
    org = Organization(**payload.model_dump(), created_by=user.id)
    db.add(org); await db.flush()
    workspace = Workspace(organization_id=org.id, name="Default workspace", slug="default")
    db.add_all([workspace, OrganizationMember(organization_id=org.id, user_id=user.id, role_key="owner"), TenantPolicy(organization_id=org.id), TenantQuota(organization_id=org.id)])
    await db.flush(); db.add(WorkspaceMember(organization_id=org.id, workspace_id=workspace.id, user_id=user.id, role_key="owner"))
    from app.services.enterprise import OWNER_PERMISSIONS, ADMIN_PERMISSIONS, MEMBER_PERMISSIONS
    for key, name, permissions in (("owner", "Owner", OWNER_PERMISSIONS), ("admin", "Administrator", ADMIN_PERMISSIONS), ("member", "Member", MEMBER_PERMISSIONS)):
        db.add(CustomRole(organization_id=org.id, key=key, name=name, permissions=sorted(permissions), is_system=True))
    audit(db, user, "organization.create", "organization", org.id, after={"name": org.name, "region": org.data_region}, organization_id=org.id)
    return {"id": org.id, "workspace_id": workspace.id}


@router.post("/workspaces", status_code=201)
async def create_workspace(payload: WorkspaceCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.manage")
    row = Workspace(organization_id=ctx.organization.id, **payload.model_dump()); db.add(row); await db.flush()
    db.add(WorkspaceMember(organization_id=ctx.organization.id, workspace_id=row.id, user_id=user.id, role_key="owner"))
    audit(db, user, "workspace.create", "workspace", row.id, after={"name": row.name}, organization_id=ctx.organization.id)
    return {"id": row.id, "name": row.name}


@router.get("/members")
async def members(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.read")
    rows = (await db.execute(select(OrganizationMember, User).join(User, User.id == OrganizationMember.user_id).where(OrganizationMember.organization_id == ctx.organization.id).order_by(User.username))).all()
    return [{"id": m.id, "user_id": u.id, "username": u.username, "email": u.email, "role_key": m.role_key, "status": m.status} for m, u in rows]


@router.post("/members", status_code=201)
async def add_member(payload: MemberCreate, ctx: TenantContext = Depends(get_tenant_context), actor: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "members.manage")
    quota = await db.get(TenantQuota, ctx.organization.id)
    count = await db.scalar(select(func.count()).select_from(OrganizationMember).where(OrganizationMember.organization_id == ctx.organization.id, OrganizationMember.status == "active"))
    if quota and count >= quota.member_limit: raise HTTPException(409, "Tenant member quota exceeded")
    user = await db.scalar(select(User).where(func.lower(User.email) == payload.email.lower()))
    if not user: raise HTTPException(404, "User must create an account before being added")
    if await db.scalar(select(OrganizationMember.id).where(OrganizationMember.organization_id == ctx.organization.id, OrganizationMember.user_id == user.id)): raise HTTPException(409, "User is already a member")
    role = await db.scalar(select(CustomRole).where(CustomRole.organization_id == ctx.organization.id, CustomRole.key == payload.role_key))
    if not role: raise HTTPException(422, "Unknown tenant role")
    member = OrganizationMember(organization_id=ctx.organization.id, user_id=user.id, role_key=payload.role_key); db.add(member)
    valid_workspaces = (await db.scalars(select(Workspace).where(Workspace.organization_id == ctx.organization.id, Workspace.id.in_(payload.workspace_ids)))).all() if payload.workspace_ids else []
    if len(valid_workspaces) != len(set(payload.workspace_ids)): raise HTTPException(422, "Workspace does not belong to organization")
    for workspace in valid_workspaces: db.add(WorkspaceMember(organization_id=ctx.organization.id, workspace_id=workspace.id, user_id=user.id, role_key=payload.role_key))
    await db.flush(); audit(db, actor, "member.add", "organization_member", member.id, after={"user_id": user.id, "role_key": member.role_key}, organization_id=ctx.organization.id)
    return {"id": member.id, "user_id": user.id}


@router.get("/roles")
async def roles(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.read")
    rows = (await db.scalars(select(CustomRole).where(CustomRole.organization_id == ctx.organization.id).order_by(CustomRole.is_system.desc(), CustomRole.name))).all()
    return [{"id": x.id, "key": x.key, "name": x.name, "permissions": x.permissions, "is_system": x.is_system} for x in rows]


@router.post("/roles", status_code=201)
async def create_role(payload: RoleCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "roles.manage")
    row = CustomRole(organization_id=ctx.organization.id, **payload.model_dump(), is_system=False); db.add(row); await db.flush()
    audit(db, user, "role.create", "role", row.id, after={"key": row.key, "permissions": row.permissions}, organization_id=ctx.organization.id)
    return {"id": row.id}


@router.post("/teams", status_code=201)
async def create_team(payload: TeamCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "members.manage")
    member_ids = set((await db.scalars(select(OrganizationMember.user_id).where(OrganizationMember.organization_id == ctx.organization.id, OrganizationMember.user_id.in_(payload.user_ids)))).all())
    if member_ids != set(payload.user_ids): raise HTTPException(422, "Team includes users outside the organization")
    row = Team(organization_id=ctx.organization.id, name=payload.name, description=payload.description); db.add(row); await db.flush()
    for user_id in member_ids: db.add(TeamMember(organization_id=ctx.organization.id, team_id=row.id, user_id=user_id))
    audit(db, user, "team.create", "team", row.id, after={"name": row.name, "member_count": len(member_ids)}, organization_id=ctx.organization.id)
    return {"id": row.id}


@router.get("/identity-providers")
async def identity_providers(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "sso.manage")
    rows = (await db.scalars(select(IdentityProvider).where(IdentityProvider.organization_id == ctx.organization.id))).all()
    return [{"id": x.id, "provider_type": x.provider_type, "name": x.name, "enabled": x.enabled, "issuer": x.issuer, "client_id": x.client_id, "metadata": x.provider_metadata, "scim_configured": bool(x.scim_token_hash)} for x in rows]


@router.post("/identity-providers", status_code=201)
async def create_identity_provider(payload: IdentityProviderCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "sso.manage")
    metadata = payload.metadata
    if payload.enabled:
        if payload.provider_type == "oidc" and not (payload.issuer.startswith("https://") and metadata.get("authorization_endpoint", "").startswith("https://") and metadata.get("jwks_uri", "").startswith("https://")): raise HTTPException(422, "Enabled OIDC requires HTTPS issuer, authorization endpoint and JWKS URI")
        if payload.provider_type == "saml" and not (metadata.get("sso_url", "").startswith("https://") and "BEGIN CERTIFICATE" in metadata.get("signing_certificate", "")): raise HTTPException(422, "Enabled SAML requires HTTPS SSO URL and signing certificate")
    values = payload.model_dump(exclude={"metadata"})
    row = IdentityProvider(organization_id=ctx.organization.id, provider_metadata=payload.metadata, **values); db.add(row); await db.flush()
    audit(db, user, "identity_provider.create", "identity_provider", row.id, after={"type": row.provider_type, "enabled": row.enabled}, organization_id=ctx.organization.id)
    return {"id": row.id}


@router.post("/identity-providers/{provider_id}/scim-token")
async def rotate_scim_token(provider_id: str, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "sso.manage")
    row = await db.scalar(select(IdentityProvider).where(IdentityProvider.id == provider_id, IdentityProvider.organization_id == ctx.organization.id, IdentityProvider.provider_type == "scim"))
    if not row: raise HTTPException(404, "SCIM provider not found")
    token, row.scim_token_hash = new_scim_token(); audit(db, user, "scim_token.rotate", "identity_provider", row.id, organization_id=ctx.organization.id)
    return {"token": token, "warning": "This token is shown once and is not recoverable"}


@router.get("/approvals")
async def approvals(status: str | None = Query(None, pattern="^(pending|approved|rejected)$"), ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    query = select(ApprovalRequest).where(ApprovalRequest.organization_id == ctx.organization.id)
    if status: query = query.where(ApprovalRequest.status == status)
    rows = (await db.scalars(query.order_by(ApprovalRequest.created_at.desc()).limit(200))).all()
    return [{"id": x.id, "action_type": x.action_type, "risk_level": x.risk_level, "status": x.status, "requested_by": x.requested_by, "decided_by": x.decided_by, "decision_note": x.decision_note, "created_at": x.created_at} for x in rows]


@router.post("/approvals", status_code=201)
async def request_approval(payload: ApprovalCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "approvals.request"); clean_payload(payload.payload)
    if payload.workspace_id and not await db.scalar(select(WorkspaceMember.id).where(WorkspaceMember.workspace_id == payload.workspace_id, WorkspaceMember.user_id == user.id, WorkspaceMember.organization_id == ctx.organization.id)): raise HTTPException(403, "Workspace access denied")
    row = ApprovalRequest(organization_id=ctx.organization.id, requested_by=user.id, **payload.model_dump()); db.add(row); await db.flush(); audit(db, user, "approval.request", "approval", row.id, after={"action_type": row.action_type, "risk_level": row.risk_level}, organization_id=ctx.organization.id)
    return {"id": row.id, "status": row.status}


@router.post("/approvals/{approval_id}/decision")
async def decide_approval(approval_id: str, payload: ApprovalDecision, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "approvals.decide")
    row = await db.scalar(select(ApprovalRequest).where(ApprovalRequest.id == approval_id, ApprovalRequest.organization_id == ctx.organization.id))
    if not row: raise HTTPException(404, "Approval not found")
    if row.status != "pending": raise HTTPException(409, "Approval is already decided")
    if row.requested_by == user.id: raise HTTPException(409, "Requester cannot approve their own high-risk action")
    row.status, row.decided_by, row.decision_note, row.decided_at = payload.decision, user.id, payload.note, datetime.now(timezone.utc)
    audit(db, user, f"approval.{payload.decision}", "approval", row.id, before={"status": "pending"}, after={"status": row.status}, organization_id=ctx.organization.id)
    return {"id": row.id, "status": row.status}


@router.get("/policy")
async def get_policy(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "org.read"); return await db.get(TenantPolicy, ctx.organization.id)


@router.put("/policy")
async def update_policy(payload: PolicyUpdate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "policy.manage")
    domains = [x.lower().strip() for x in payload.allowed_email_domains]
    if any(not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", x) for x in domains): raise HTTPException(422, "Invalid allowed email domain")
    row = await db.get(TenantPolicy, ctx.organization.id); before = {"require_sso": row.require_sso, "retention_days": row.retention_days}
    for key, value in payload.model_dump().items(): setattr(row, key, domains if key == "allowed_email_domains" else value)
    audit(db, user, "policy.update", "tenant_policy", ctx.organization.id, before=before, after={"require_sso": row.require_sso, "retention_days": row.retention_days}, organization_id=ctx.organization.id)
    return row


@router.get("/quota")
async def get_quota(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "billing.read"); return await db.get(TenantQuota, ctx.organization.id)


@router.put("/quota")
async def update_quota(payload: QuotaUpdate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "billing.manage")
    row = await db.get(TenantQuota, ctx.organization.id)
    if payload.monthly_cost_limit > row.monthly_cost_limit * 2:
        raise HTTPException(409, "Budget increases above 2x require an approved raise_model_budget request")
    for key, value in payload.model_dump().items(): setattr(row, key, value)
    audit(db, user, "quota.update", "tenant_quota", ctx.organization.id, after=payload.model_dump(), organization_id=ctx.organization.id)
    return row


@router.post("/legal-holds", status_code=201)
async def create_legal_hold(payload: LegalHoldCreate, ctx: TenantContext = Depends(get_tenant_context), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "legal_hold.manage"); clean_payload(payload.scope)
    row = LegalHold(organization_id=ctx.organization.id, created_by=user.id, **payload.model_dump()); db.add(row); await db.flush(); audit(db, user, "legal_hold.create", "legal_hold", row.id, after={"name": row.name}, organization_id=ctx.organization.id)
    return {"id": row.id, "status": row.status}


@router.get("/audit-export")
async def export_audit(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "audit.export")
    user_ids = select(OrganizationMember.user_id).where(OrganizationMember.organization_id == ctx.organization.id)
    rows = (await db.scalars(select(AuditLog).where(AuditLog.organization_id == ctx.organization.id).order_by(AuditLog.created_at.desc()).limit(5000))).all()
    payload = [{"id": x.id, "actor_id": x.user_id, "action": x.action, "target_type": x.target_type, "target_id": x.target_id, "before": x.before_data, "after": x.after_data, "created_at": x.created_at.isoformat()} for x in rows]
    return JSONResponse(payload, headers={"Content-Disposition": "attachment; filename=tenant-audit.json", "Cache-Control": "no-store"})


@router.get("/operations")
async def tenant_operations(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    require_permission(ctx, "billing.read")
    user_ids = select(OrganizationMember.user_id).where(OrganizationMember.organization_id == ctx.organization.id)
    members_count = await db.scalar(select(func.count()).select_from(OrganizationMember).where(OrganizationMember.organization_id == ctx.organization.id, OrganizationMember.status == "active"))
    usage = (await db.execute(select(func.coalesce(func.sum(ModelUsage.prompt_tokens + ModelUsage.completion_tokens), 0), func.coalesce(func.sum(ModelUsage.cost), 0)).where(ModelUsage.user_id.in_(user_ids)))).one()
    documents = await db.scalar(select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.user_id.in_(user_ids), KnowledgeDocument.status != "deleted"))
    quota = await db.get(TenantQuota, ctx.organization.id)
    sla = await db.scalar(select(TenantSLA).where(TenantSLA.organization_id == ctx.organization.id).order_by(TenantSLA.period.desc()))
    return {"members": {"used": int(members_count or 0), "limit": quota.member_limit}, "model_tokens": {"used": int(usage[0]), "limit": quota.monthly_model_tokens}, "model_cost": {"used": round(float(usage[1]), 4), "limit": quota.monthly_cost_limit}, "knowledge_documents": int(documents or 0), "data_region": ctx.organization.data_region, "sla": {"period": sla.period, "availability": sla.availability, "p95_latency_ms": sla.p95_latency_ms, "incidents": sla.incidents, "error_budget_remaining": sla.error_budget_remaining} if sla else None}


async def scim_provider(credentials: HTTPAuthorizationCredentials = Depends(scim_bearer), db: AsyncSession = Depends(get_db)) -> IdentityProvider:
    token_hash = hash_scim_token(credentials.credentials)
    if db.bind and db.bind.dialect.name == "postgresql": await db.execute(select(func.set_config("app.scim_token_hash", token_hash, True)))
    provider = await db.scalar(select(IdentityProvider).where(IdentityProvider.scim_token_hash == token_hash, IdentityProvider.provider_type == "scim", IdentityProvider.enabled.is_(True)))
    if not provider: raise HTTPException(401, "Invalid SCIM bearer token")
    await set_db_context(db, "scim-service", provider.organization_id)
    return provider


@scim_router.get("/ServiceProviderConfig")
async def scim_config(_provider: IdentityProvider = Depends(scim_provider)):
    return {"schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"], "patch": {"supported": False}, "bulk": {"supported": False}, "filter": {"supported": True, "maxResults": 100}, "changePassword": {"supported": False}, "sort": {"supported": False}, "etag": {"supported": False}, "authenticationSchemes": [{"type": "oauthbearertoken", "name": "Bearer Token", "primary": True}]}


@scim_router.get("/Users")
async def scim_users(startIndex: int = Query(1, ge=1), count: int = Query(100, ge=1, le=100), provider: IdentityProvider = Depends(scim_provider), db: AsyncSession = Depends(get_db)):
    query = select(User).join(OrganizationMember, OrganizationMember.user_id == User.id).where(OrganizationMember.organization_id == provider.organization_id).offset(startIndex - 1).limit(count)
    users = (await db.scalars(query)).all()
    resources = [{"schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"], "id": x.id, "userName": x.email, "displayName": x.username, "active": x.is_active} for x in users]
    return {"schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"], "totalResults": len(resources), "startIndex": startIndex, "itemsPerPage": len(resources), "Resources": resources}


@scim_router.post("/Users", status_code=201)
async def scim_create_user(payload: ScimUserCreate, provider: IdentityProvider = Depends(scim_provider), db: AsyncSession = Depends(get_db)):
    email = payload.userName.lower()
    policy = await db.get(TenantPolicy, provider.organization_id)
    if policy.allowed_email_domains and email.rsplit("@", 1)[-1] not in policy.allowed_email_domains: raise HTTPException(422, "Email domain is not allowed by tenant policy")
    user = await db.scalar(select(User).where(func.lower(User.email) == email))
    if not user:
        username = (payload.displayName or email.split("@", 1)[0])[:50]
        if await db.scalar(select(User.id).where(func.lower(User.username) == username.lower())): username = f"{username[:40]}-{provider.organization_id[:6]}"
        user = User(username=username, email=email, password_hash=await run_in_threadpool(hash_password, new_scim_token()[0]), is_active=payload.active)
        db.add(user); await db.flush()
    membership = await db.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == provider.organization_id, OrganizationMember.user_id == user.id))
    if not membership: db.add(OrganizationMember(organization_id=provider.organization_id, user_id=user.id, role_key="member"))
    return {"schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"], "id": user.id, "userName": user.email, "displayName": user.username, "active": user.is_active}
