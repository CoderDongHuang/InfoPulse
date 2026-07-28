"""
InfoPulse — Database Connection
================================
SQLAlchemy async engine + session factory.
Engine is created lazily so the app can import without a running database.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# Lazy-initialized engine and session factory
_engine = None
_async_session = None


def _get_engine():
    """Create or return the async engine (lazy initialization)."""
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.DATABASE_URL

        # SQLite needs different args than PostgreSQL
        if "sqlite" in url:
            _engine = create_async_engine(url, echo=False)
        else:
            _engine = create_async_engine(
                url,
                echo=False,
                pool_size=10,
                max_overflow=20,
            )
    return _engine


def _get_sessionmaker():
    """Create or return the async session factory."""
    global _async_session
    if _async_session is None:
        _async_session = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session


async def init_db():
    """Verify connectivity; optionally create tables in disposable development setups."""
    engine = _get_engine()
    async with engine.begin() as conn:
        if get_settings().AUTO_CREATE_TABLES:
            await conn.run_sync(Base.metadata.create_all)
        else:
            await conn.execute(text("SELECT 1"))


async def close_db():
    """Dispose engine on application shutdown."""
    global _engine, _async_session
    if _engine is not None:
        await _engine.dispose()
        _engine = None
    _async_session = None


async def get_db() -> AsyncSession:
    """Dependency: yield an async database session."""
    sessionmaker = _get_sessionmaker()
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
