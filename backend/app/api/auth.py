"""
InfoPulse — Auth API Routes
============================
POST /api/v1/auth/register  — Register a new user
POST /api/v1/auth/login     — Login and get tokens
POST /api/v1/auth/refresh   — Refresh access token
GET  /api/v1/auth/me        — Get current user profile
PUT  /api/v1/auth/me        — Update current user profile
"""

import hmac
import re
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select, text
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    UserUpdateRequest,
    AccountDeleteRequest,
)
from app.schemas.workflows import RefreshTokenRequest
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/sso/exchange", response_model=TokenResponse)
async def sso_exchange(
    x_sso_proxy_secret: str = Header(alias="X-SSO-Proxy-Secret"),
    x_sso_organization: str = Header(alias="X-SSO-Organization"),
    x_sso_email: str = Header(alias="X-SSO-Email"),
    x_sso_subject: str = Header(alias="X-SSO-Subject"),
    db: AsyncSession = Depends(get_db),
):
    """Exchange identity headers asserted by a trusted OIDC/SAML broker."""
    from app.config import get_settings
    from app.models.enterprise import IdentityProvider, Organization, OrganizationMember, TenantPolicy
    from app.core.security import hash_password
    from app.services.enterprise import new_scim_token, set_db_context

    expected = get_settings().SSO_PROXY_SECRET
    if len(expected) < 32 or not hmac.compare_digest(x_sso_proxy_secret, expected):
        raise HTTPException(status_code=401, detail="Invalid SSO proxy credential")
    if not x_sso_subject.strip() or len(x_sso_subject) > 500:
        raise HTTPException(status_code=422, detail="Invalid SSO subject")
    email = x_sso_email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=422, detail="Invalid verified email")
    if db.bind and db.bind.dialect.name == "postgresql": await db.execute(text("SELECT set_config('app.sso_org_slug', :slug, true)"), {"slug": x_sso_organization})
    org = await db.scalar(select(Organization).where(Organization.slug == x_sso_organization, Organization.status == "active"))
    if not org: raise HTTPException(status_code=404, detail="SSO organization not found")
    await set_db_context(db, "sso-service", org.id)
    provider = await db.scalar(select(IdentityProvider.id).where(IdentityProvider.organization_id == org.id, IdentityProvider.provider_type.in_(["oidc", "saml"]), IdentityProvider.enabled.is_(True)))
    if not provider: raise HTTPException(status_code=403, detail="No enabled SSO provider for organization")
    policy = await db.get(TenantPolicy, org.id)
    if policy.allowed_email_domains and email.rsplit("@", 1)[-1] not in policy.allowed_email_domains:
        raise HTTPException(status_code=403, detail="Email domain is not allowed by tenant policy")
    user = await db.scalar(select(User).where(func.lower(User.email) == email))
    if not user:
        base = re.sub(r"[^a-zA-Z0-9_.-]", "-", email.split("@", 1)[0])[:40] or "sso-user"
        username = base if not await db.scalar(select(User.id).where(func.lower(User.username) == base.lower())) else f"{base}-{org.id[:6]}"
        user = User(username=username, email=email, password_hash=await run_in_threadpool(hash_password, new_scim_token()[0]), is_active=True)
        db.add(user); await db.flush()
    membership = await db.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == org.id, OrganizationMember.user_id == user.id))
    if not membership:
        membership = OrganizationMember(organization_id=org.id, user_id=user.id, role_key="member"); db.add(membership)
    elif membership.status != "active": raise HTTPException(status_code=403, detail="Organization membership is inactive")
    return auth_service._generate_tokens(user)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new account. Returns access + refresh tokens."""
    try:
        return await auth_service.register_user(db, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with username/email + password. Returns tokens."""
    try:
        return await auth_service.login_user(db, data.username, data.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Rotate an access token using a refresh token."""
    from app.core.security import create_access_token, create_refresh_token, verify_token
    from app.services.auth_service import get_user_by_id

    token_payload = verify_token(payload.refresh_token)
    if not token_payload or token_payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新凭证无效或已过期")
    current_user = await get_user_by_id(db, token_payload.get("sub", ""))
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已停用")
    token_data = {"sub": current_user.id, "username": current_user.username}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        token_type="bearer",
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's profile."""
    try:
        return await auth_service.update_user(db, current_user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    data: AccountDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete an account and its private knowledge objects."""
    from sqlalchemy import select
    from starlette.concurrency import run_in_threadpool
    from app.core.security import verify_password
    from app.models.intelligence import KnowledgeDocument
    from app.services.knowledge import delete_document
    from app.services.enterprise import ensure_not_held

    if not await run_in_threadpool(verify_password, data.password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password verification failed")
    await ensure_not_held(db, current_user.id)
    documents = (await db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.user_id == current_user.id))).all()
    for document in documents:
        await delete_document(db, document, strict_storage=True)
    await db.delete(current_user)
