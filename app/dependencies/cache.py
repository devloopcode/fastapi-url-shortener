from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis

from app.cache.analytics_cache import AnalyticsCache
from app.cache.client import get_redis
from app.cache.rate_limiter import SlidingWindowRateLimiter
from app.cache.url_cache import URLCache


async def get_url_cache(redis: Redis = Depends(get_redis)) -> URLCache:
    return URLCache(redis)


async def get_analytics_cache(redis: Redis = Depends(get_redis)) -> AnalyticsCache:
    return AnalyticsCache(redis)


async def get_rate_limiter(redis: Redis = Depends(get_redis)) -> SlidingWindowRateLimiter:
    return SlidingWindowRateLimiter(redis)


RedisClient = Annotated[Redis, Depends(get_redis)]
URLCacheDep = Annotated[URLCache, Depends(get_url_cache)]
AnalyticsCacheDep = Annotated[AnalyticsCache, Depends(get_analytics_cache)]
RateLimiterDep = Annotated[SlidingWindowRateLimiter, Depends(get_rate_limiter)]
