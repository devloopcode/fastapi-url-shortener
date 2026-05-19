from __future__ import annotations

import time
import uuid

from redis.asyncio import Redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Atomic sliding-window check implemented as a Lua script.
# All reads, writes, and the allow/deny decision happen in one round-trip with
# no interleaving — eliminates the race condition in the old pipeline approach
# where a rejected request could remove a concurrent request's zadd entry.
_SLIDING_WINDOW_SCRIPT = """
local key          = KEYS[1]
local now          = tonumber(ARGV[1])
local window_start = tonumber(ARGV[2])
local limit        = tonumber(ARGV[3])
local window       = tonumber(ARGV[4])
local req_id       = ARGV[5]

redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)
local count = redis.call('ZCARD', key)

if count >= limit then
    local reset_after = math.ceil(window - (now - window_start)) + 1
    return {0, 0, reset_after}
end

redis.call('ZADD', key, now, req_id)
redis.call('EXPIRE', key, window)
return {1, limit - count - 1, window}
"""


class SlidingWindowRateLimiter:
    """
    Redis sliding window rate limiter using a Lua script for atomicity.

    Each key maps to a sorted set where members are unique request IDs
    and scores are Unix timestamps. The Lua script atomically:
      1. Removes entries older than the window.
      2. Counts remaining entries.
      3. If count < limit, records this request and returns allowed=True.
      4. Otherwise returns allowed=False without modifying the set.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._script_sha: str | None = None

    async def _get_sha(self) -> str:
        if self._script_sha is None:
            self._script_sha = await self._redis.script_load(_SLIDING_WINDOW_SCRIPT)
        return self._script_sha

    async def is_allowed(
        self,
        identifier: str,
        *,
        limit: int,
        window: int,
        endpoint: str = "global",
    ) -> tuple[bool, int, int]:
        """
        Returns (allowed, remaining, reset_after_seconds).
        """
        key = f"ratelimit:{identifier}:{endpoint}"
        now = time.time()
        window_start = now - window
        req_id = str(uuid.uuid4())

        sha = await self._get_sha()
        result = await self._redis.evalsha(
            sha,
            1,
            key,
            str(now),
            str(window_start),
            str(limit),
            str(window),
            req_id,
        )

        allowed = bool(result[0])
        remaining = int(result[1])
        reset_after = int(result[2])

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                identifier=identifier,
                endpoint=endpoint,
                limit=limit,
            )

        return allowed, remaining, reset_after

    async def get_anonymous_limit(self) -> tuple[int, int]:
        return settings.ANONYMOUS_RATE_LIMIT, settings.ANONYMOUS_RATE_LIMIT_WINDOW

    async def get_user_limit(self) -> tuple[int, int]:
        return settings.RATE_LIMIT_REQUESTS, settings.RATE_LIMIT_WINDOW
