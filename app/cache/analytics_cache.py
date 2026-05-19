from __future__ import annotations

import json
from typing import Any, Optional

from redis.asyncio import Redis

from app.core.config import settings

_QUEUE_KEY = "analytics:queue"
_SUMMARY_PREFIX = "analytics:summary:"


class AnalyticsCache:
    """
    Two responsibilities:
      1. Acts as a write buffer — click events are pushed here first
         so redirects return immediately without waiting on Postgres.
      2. Caches aggregated summary results to avoid hitting the DB
         on every dashboard request.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    # ── Event queue ──────────────────────────────────────────────────────────

    async def push_event(self, event: dict[str, Any]) -> None:
        await self._redis.rpush(_QUEUE_KEY, json.dumps(event))

    async def pop_events(self, count: int = 100) -> list[dict[str, Any]]:
        # LMPOP is atomic (Redis 7+): pops up to `count` elements in a single round-trip.
        # The old lrange+ltrim pipeline was not atomic — a crash between the two commands
        # would silently lose events already fetched but not yet trimmed.
        result = await self._redis.lmpop(1, _QUEUE_KEY, direction="LEFT", count=count)
        if not result:
            return []
        _key, raw_events = result
        return [json.loads(e) for e in raw_events]

    async def queue_length(self) -> int:
        return await self._redis.llen(_QUEUE_KEY)

    # ── Summary cache ─────────────────────────────────────────────────────────

    async def get_summary(self, short_code: str) -> Optional[dict[str, Any]]:
        raw = await self._redis.get(f"{_SUMMARY_PREFIX}{short_code}")
        return json.loads(raw) if raw else None

    async def set_summary(self, short_code: str, data: dict[str, Any]) -> None:
        await self._redis.setex(
            f"{_SUMMARY_PREFIX}{short_code}",
            settings.ANALYTICS_CACHE_TTL,
            json.dumps(data),
        )

    async def invalidate_summary(self, short_code: str) -> None:
        await self._redis.delete(f"{_SUMMARY_PREFIX}{short_code}")
