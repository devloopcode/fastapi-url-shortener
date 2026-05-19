from __future__ import annotations

import time

from redis.asyncio import Redis

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SlidingWindowRateLimiter:
    """
    Redis sliding window rate limiter using sorted sets.

    Each key maps to a sorted set where members are unique request IDs
    and scores are Unix timestamps.  On each request we:
      1. Remove entries older than the window.
      2. Count remaining entries.
      3. If count < limit, add this request and return True.
      4. Otherwise return False (limit exceeded).

    This gives precise per-second granularity without the boundary-burst
    problem of fixed windows.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

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

        pipe = self._redis.pipeline(transaction=True)
        pipe.zremrangebyscore(key, "-inf", window_start)
        pipe.zcard(key)
        pipe.zadd(key, {f"{now}:{id(pipe)}": now})
        pipe.expire(key, window)
        results = await pipe.execute()

        current_count = results[1]  # count BEFORE this request

        if current_count >= limit:
            # Undo the zadd — don't count rejected requests
            await self._redis.zremrangebyscore(key, now, now + 0.001)
            reset_after = int(window_start + window - now) + 1
            logger.warning(
                "rate_limit_exceeded",
                identifier=identifier,
                endpoint=endpoint,
                limit=limit,
            )
            return False, 0, reset_after

        remaining = limit - current_count - 1
        return True, remaining, window

    async def get_anonymous_limit(self) -> tuple[int, int]:
        return settings.ANONYMOUS_RATE_LIMIT, settings.ANONYMOUS_RATE_LIMIT_WINDOW

    async def get_user_limit(self) -> tuple[int, int]:
        return settings.RATE_LIMIT_REQUESTS, settings.RATE_LIMIT_WINDOW
