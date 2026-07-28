"""
InfoPulse — Auth Service
=========================
Business logic for user registration, login, and profile management.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.config import get_settings
from app.schemas.auth import (
    TokenResponse,
    UserRegisterRequest,
    UserResponse,
    UserUpdateRequest,
)


async def register_user(db: AsyncSession, data: UserRegisterRequest) -> TokenResponse:
    """Register a new user and return JWT tokens."""
    # Check uniqueness
    existing = await db.execute(
        select(User).where(
            (func.lower(User.username) == data.username.lower())
            | (func.lower(User.email) == str(data.email).lower())
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("用户名或邮箱已被注册")

    # Create user
    user = User(
        username=data.username,
        email=str(data.email).lower(),
        password_hash=await run_in_threadpool(hash_password, data.password),
        is_admin=str(data.email).lower() in {email.lower() for email in get_settings().ADMIN_EMAILS},
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ValueError("用户名或邮箱已被注册") from exc
    await db.refresh(user)

    return _generate_tokens(user)


async def login_user(db: AsyncSession, username: str, password: str) -> TokenResponse:
    """Authenticate user and return JWT tokens."""
    result = await db.execute(
        select(User).where(
            (func.lower(User.username) == username.lower())
            | (func.lower(User.email) == username.lower())
        )
    )
    user = result.scalar_one_or_none()

    if not user or not await run_in_threadpool(verify_password, password, user.password_hash):
        raise ValueError("用户名、邮箱或密码不正确")

    if not user.is_active:
        raise ValueError("账号已停用")

    return _generate_tokens(user)


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Fetch a user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def update_user(db: AsyncSession, user_id: str, data: UserUpdateRequest) -> UserResponse:
    """Update user profile fields."""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise ValueError("User not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


def _generate_tokens(user: User) -> TokenResponse:
    """Generate access + refresh token pair for a user."""
    token_data = {"sub": user.id, "username": user.username}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )
