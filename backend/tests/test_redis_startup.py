"""Optional Redis startup must not publish an unusable global client."""
import unittest
from unittest.mock import AsyncMock, patch

from app.core import redis


class RedisStartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_ping_releases_pool_and_leaves_optional_consumers_disabled(self):
        candidate = AsyncMock()
        candidate.ping.side_effect = ConnectionError("fixture unavailable")
        with patch.object(redis, "redis_client", None), patch.object(redis.aioredis, "from_url", return_value=candidate):
            with self.assertRaises(ConnectionError):
                await redis.init_redis()
            self.assertIsNone(redis.redis_client)
            candidate.aclose.assert_awaited_once()

    async def test_success_publishes_only_after_ping(self):
        candidate = AsyncMock()
        async def ping():
            self.assertIsNone(redis.redis_client)
        candidate.ping.side_effect = ping
        with patch.object(redis, "redis_client", None), patch.object(redis.aioredis, "from_url", return_value=candidate):
            await redis.init_redis()
            self.assertIs(redis.redis_client, candidate)
            candidate.aclose.assert_not_awaited()
