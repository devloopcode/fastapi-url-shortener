from __future__ import annotations

from typing import Optional

# pyrefly: ignore [missing-import]
import redis.asyncio as aioredis
# pyrefly: ignore [missing-import]
from redis.asyncio import Redis

from app.core.config import settings

_redis_client: Optional[Redis] = None


async def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.REDIS_POOL_SIZE,
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
