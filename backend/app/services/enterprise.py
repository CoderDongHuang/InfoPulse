"""Tenant provisioning and permission evaluation."""
import hashlib
import secrets
import re
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import CustomRole, LegalHold, Organization, OrganizationMember, TenantPolicy, TenantQuota, Workspace, WorkspaceMember
from app.models.user import User

OWNER_PERMISSIONS = {"org.read", "org.manage", "members.manage", "roles.manage", "sso.manage", "approvals.request", "approvals.decide", "audit.export", "legal_hold.manage", "policy.manage", "billing.read", "billing.manage", "sla.read", "developer.read", "developer.manage", "integrations.install", "integrations.approve", "agents.read", "agents.run", "agents.manage", "agents.approve"}
ADMIN_PERMISSIONS = OWNER_PERMISSIONS - {"org.manage"}
MEMBER_PERMISSIONS = {"org.read", "approvals.request", "billing.read", "sla.read"}


@dataclass
class TenantContext:
    organization: Organization
    membership: OrganizationMember
    workspace: Workspace | None
    permissions: set[str]


async def set_db_context(db: AsyncSession, user_id: str, organization_id: str = "") -> None:
    if db.bind and db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": user_id})
        await db.execute(text("SELECT set_config('app.organization_id', :organization_id, true)"), {"organization_id": organization_id})


async def provision_personal_tenant(db: AsyncSession, user: User) -> Organization:
    slug_base = re.sub(r"[^a-z0-9]+", "-", user.username.lower()).strip("-")[:45] or "workspace"
    slug = f"{slug_base}-{user.id[:8]}"
    org = Organization(name=f"{user.username}'s organization", slug=slug, data_region="global", created_by=user.id)
    db.add(org)
    await db.flush()
    workspace = Workspace(organization_id=org.id, name="Personal workspace", slug="personal")
    db.add_all([
        workspace,
        OrganizationMember(organization_id=org.id, user_id=user.id, role_key="owner"),
        TenantPolicy(organization_id=org.id),
        TenantQuota(organization_id=org.id),
    ])
    await db.flush()
    db.add(WorkspaceMember(organization_id=org.id, workspace_id=workspace.id, user_id=user.id, role_key="owner"))
    for key, name, permissions in (("owner", "Owner", OWNER_PERMISSIONS), ("admin", "Administrator", ADMIN_PERMISSIONS), ("member", "Member", MEMBER_PERMISSIONS)):
        db.add(CustomRole(organization_id=org.id, key=key, name=name, permissions=sorted(permissions), is_system=True))
    return org


async def resolve_tenant(db: AsyncSession, user: User, organization_id: str | None, workspace_id: str | None) -> TenantContext:
    await set_db_context(db, user.id)
    query = select(OrganizationMember).where(OrganizationMember.user_id == user.id, OrganizationMember.status == "active")
    if organization_id:
        query = query.where(OrganizationMember.organization_id == organization_id)
    membership = (await db.scalars(query.order_by(OrganizationMember.joined_at))).first()
    if not membership:
        raise HTTPException(status_code=403, detail="No active organization membership")
    await set_db_context(db, user.id, membership.organization_id)
    organization = await db.get(Organization, membership.organization_id)
    workspace = None
    if workspace_id:
        workspace_membership = await db.scalar(select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user.id, WorkspaceMember.organization_id == membership.organization_id))
        if not workspace_membership:
            raise HTTPException(status_code=403, detail="Workspace access denied")
        workspace = await db.get(Workspace, workspace_id)
    permissions = OWNER_PERMISSIONS if membership.role_key == "owner" else ADMIN_PERMISSIONS if membership.role_key == "admin" else None
    if permissions is None:
        role = await db.scalar(select(CustomRole).where(CustomRole.organization_id == membership.organization_id, CustomRole.key == membership.role_key))
        permissions = set(role.permissions if role else MEMBER_PERMISSIONS)
    return TenantContext(organization, membership, workspace, set(permissions))


def require_permission(context: TenantContext, permission: str) -> None:
    if permission not in context.permissions:
        raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")


def new_scim_token() -> tuple[str, str]:
    token = "scim_" + secrets.token_urlsafe(32)
    return token, hashlib.sha256(token.encode()).hexdigest()


def hash_scim_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def ensure_not_held(db: AsyncSession, user_id: str, workspace_id: str | None = None) -> None:
    organization_ids = (await db.scalars(select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user_id, OrganizationMember.status == "active"))).all()
    holds = (await db.scalars(select(LegalHold).where(LegalHold.organization_id.in_(organization_ids), LegalHold.status == "active"))).all() if organization_ids else []
    if any(hold.scope.get("all") or user_id in hold.scope.get("user_ids", []) or (workspace_id and workspace_id in hold.scope.get("workspace_ids", [])) for hold in holds):
        raise HTTPException(status_code=409, detail="Deletion is blocked by an active legal hold")
