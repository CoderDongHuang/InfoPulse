"""
InfoPulse — Redis Connection
=============================
Async Redis client for caching and task queue.
"""

import redis.asyncio as aioredis
from app.config import get_settings

settings = get_settings()

redis_client: aioredis.Redis | None = None


async def init_redis():
    """Initialize Redis connection pool on application startup."""
    global redis_client
    candidate = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    # Publish only a verified client. Optional consumers must see None when
    # local startup continues without Redis, not a broken connection pool.
    try:
        await candidate.ping()
    except BaseException:
        await candidate.aclose()
        raise
    redis_client = candidate


async def close_redis():
    """Close Redis connection on application shutdown."""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


async def get_redis() -> aioredis.Redis:
    """Dependency: return the Redis client."""
    if redis_client is None:
        await init_redis()
    return redis_client
