from __future__ import annotations

import json
from typing import Optional

from redis.asyncio import Redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_URL_PREFIX = "url:"
_HOT_PREFIX = "hot:"


def _key(short_code: str) -> str:
    return f"{_URL_PREFIX}{short_code}"


def _hot_key(short_code: str) -> str:
    return f"{_HOT_PREFIX}{short_code}"


class URLCache:
    """
    Cache-aside layer for URL lookups.

    Stores serialized URL data keyed by short_code with a configurable TTL.
    Tracks click frequency via a separate hot-URL counter so we can extend
    TTL on popular links before they fall out of cache.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get(self, short_code: str) -> Optional[dict]:
        raw = await self._redis.get(_key(short_code))
        if raw is None:
            logger.debug("url_cache_miss", short_code=short_code)
            return None
        logger.debug("url_cache_hit", short_code=short_code)
        return json.loads(raw)

    async def set(self, short_code: str, data: dict, ttl: int | None = None) -> None:
        ttl = ttl or settings.URL_CACHE_TTL
        await self._redis.setex(_key(short_code), ttl, json.dumps(data))

    async def delete(self, short_code: str) -> None:
        await self._redis.delete(_key(short_code), _hot_key(short_code))

    async def track_click(self, short_code: str) -> int:
        """Increment hot-URL counter and extend cache TTL when threshold is crossed."""
        count = await self._redis.incr(_hot_key(short_code))
        # Refresh window every 1000 clicks to keep hot URLs in cache
        await self._redis.expire(_hot_key(short_code), 3600)

        if count >= settings.HOT_URL_CLICK_THRESHOLD:
            # Extend the URL payload TTL for hot links
            await self._redis.expire(_key(short_code), settings.URL_CACHE_TTL * 2)

        return count

    async def invalidate_many(self, short_codes: list[str]) -> None:
        if short_codes:
            keys = [_key(c) for c in short_codes] + [_hot_key(c) for c in short_codes]
            await self._redis.delete(*keys)
