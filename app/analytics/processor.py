from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from app.cache.analytics_cache import AnalyticsCache
from app.config import settings
from app.core.logging import get_logger
from app.db.session import AsyncSessionFactory
from app.repositories.click_event import ClickEventRepository
from app.repositories.url import URLRepository

logger = get_logger(__name__)


class AnalyticsProcessor:
    """
    Background worker that drains the Redis analytics queue and persists
    click events to PostgreSQL in batches.

    Runs as an asyncio Task for the lifetime of the application process.
    Batching amortises DB round-trips; the short flush interval keeps
    analytics data fresh without hammering Postgres.
    """

    def __init__(self, analytics_cache: AnalyticsCache) -> None:
        self._cache = analytics_cache
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run(), name="analytics-processor")
        logger.info("analytics_processor_started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # Final flush on shutdown
        await self._flush()
        logger.info("analytics_processor_stopped")

    async def _run(self) -> None:
        while self._running:
            try:
                await self._flush()
            except Exception as exc:
                logger.error("analytics_flush_error", error=str(exc))
            await asyncio.sleep(settings.ANALYTICS_FLUSH_INTERVAL)

    async def _flush(self) -> None:
        queue_len = await self._cache.queue_length()
        if queue_len == 0:
            return

        events = await self._cache.pop_events(settings.ANALYTICS_BATCH_SIZE)
        if not events:
            return

        logger.info("analytics_flush", count=len(events))

        async with AsyncSessionFactory() as session:
            click_repo = ClickEventRepository(session)
            url_repo = URLRepository(session)

            db_events: list[dict[str, Any]] = []
            url_ids: set[uuid.UUID] = set()

            for raw in events:
                try:
                    url_id = uuid.UUID(raw["short_url_id"])
                    db_events.append(
                        {
                            "short_url_id": url_id,
                            "visitor_hash": raw.get("visitor_hash"),
                            "country": raw.get("country"),
                            "city": raw.get("city"),
                            "referrer": raw.get("referrer"),
                            "user_agent": raw.get("user_agent"),
                            "browser": raw.get("browser"),
                            "os": raw.get("os"),
                            "device": raw.get("device"),
                            "created_at": datetime.fromisoformat(raw["timestamp"]),
                        }
                    )
                    url_ids.add(url_id)
                except Exception as exc:
                    logger.error("analytics_event_parse_error", error=str(exc), raw=raw)

            if db_events:
                await click_repo.bulk_insert(db_events)

            # Bulk increment click counts
            for url_id in url_ids:
                count = sum(1 for e in db_events if e["short_url_id"] == url_id)
                for _ in range(count):
                    await url_repo.increment_click_count(url_id)

            await session.commit()
