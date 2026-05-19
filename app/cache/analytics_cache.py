from __future__ import annotations

import json
from typing import Any, Optional

from redis.asyncio import Redis

from app.config import settings

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
        pipe = self._redis.pipeline()
        pipe.lrange(_QUEUE_KEY, 0, count - 1)
        pipe.ltrim(_QUEUE_KEY, count, -1)
        results = await pipe.execute()
        raw_events = results[0]
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
