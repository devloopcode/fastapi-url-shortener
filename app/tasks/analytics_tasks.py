from __future__ import annotations

from app.analytics.processor import AnalyticsProcessor
from app.cache.analytics_cache import AnalyticsCache

# Module-level singleton — started/stopped by the lifespan handler
_processor: AnalyticsProcessor | None = None


async def start_analytics_worker(analytics_cache: AnalyticsCache) -> None:
    global _processor
    _processor = AnalyticsProcessor(analytics_cache)
    _processor.start()


async def stop_analytics_worker() -> None:
    global _processor
    if _processor:
        await _processor.stop()
        _processor = None
