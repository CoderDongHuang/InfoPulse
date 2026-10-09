"""Database-backed, cross-worker rate limits for authentication and generation."""
import hashlib
import logging
import time

from sqlalchemy import delete
from starlette.responses import JSONResponse

from app.config import get_settings
from app.core.database import _get_sessionmaker
from app.core.security import verify_token
from app.models.rate_limit import RateLimitBucket

logger = logging.getLogger(__name__)
AUTH_LIMITS = {"/api/v1/auth/login": 10, "/api/v1/auth/register": 5,
               "/api/v1/auth/refresh": 30, "/api/v1/auth/sso/exchange": 10,
               "/api/v1/platform/oauth/token": 20}
GENERATIONS = {"/api/v1/insights/analyze", "/api/v1/mouthpiece/generate",
               "/api/v1/timeline/build", "/api/v1/hot-search/explain"}


async def consume_window(sessions, identity: str, limit: int, at: int) -> bool:
    start = at // 60 * 60
    key = hashlib.sha256(identity.encode()).hexdigest()
    async with sessions() as db:
        if db.bind.dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            from sqlalchemy.dialects.postgresql import insert
        stmt = insert(RateLimitBucket).values(key=key, window_start=start, requests=1)
        stmt = stmt.on_conflict_do_update(
            index_elements=["key", "window_start"],
            set_={"requests": RateLimitBucket.requests + 1},
            where=RateLimitBucket.requests < limit,
        ).returning(RateLimitBucket.requests)
        allowed = (await db.scalar(stmt)) is not None
        await db.execute(delete(RateLimitBucket).where(RateLimitBucket.window_start < start - 120))
        await db.commit()
        return allowed


class RateLimitMiddleware:
    def __init__(self, app, sessions=None):
        self.app = app
        self.sessions = sessions

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        path = scope["path"]
        limit = AUTH_LIMITS.get(path)
        identity = f"{path}:{(scope.get('client') or ('unknown',))[0]}"
        if limit is None:
            is_generation = path in GENERATIONS or (
                path.startswith(("/api/v1/agent/", "/api/v1/reports", "/api/v1/analyses"))
                and path.endswith(("/messages", "/retry", "/generate")))
            if not is_generation:
                return await self.app(scope, receive, send)
            headers = dict(scope.get("headers", []))
            auth = headers.get(b"authorization", b"").decode("latin1")
            payload = verify_token(auth[7:]) if auth.lower().startswith("bearer ") else None
            if not payload or payload.get("type") != "access" or not payload.get("sub"):
                return await self.app(scope, receive, send)
            limit = get_settings().GENERATION_REQUESTS_PER_MINUTE
            identity = f"generation:{payload['sub']}"
        at = int(time.time())
        try:
            allowed = await consume_window(self.sessions or _get_sessionmaker(), identity, limit, at)
        except Exception:
            logger.exception("Rate limit storage unavailable")
            return await JSONResponse({"detail": "Rate limit storage unavailable"}, status_code=503)(scope, receive, send)
        if not allowed:
            return await JSONResponse({"detail": "Request rate limit exceeded"}, status_code=429,
                headers={"Retry-After": str(60 - at % 60)})(scope, receive, send)
        await self.app(scope, receive, send)
