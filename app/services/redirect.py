from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.events import ClickEvent
from app.cache.analytics_cache import AnalyticsCache
from app.cache.url_cache import URLCache
from app.core.exceptions import URLExpiredError, URLNotFoundError
from app.core.logging import get_logger
from app.repositories.url import URLRepository
from app.utils.user_agent_parser import parse_user_agent

logger = get_logger(__name__)


class RedirectService:
    """
    Critical-path service — every short link click goes through here.

    Priority order:
      1. Redis cache lookup  (sub-millisecond)
      2. PostgreSQL fallback (write result back to cache)
      3. Async analytics event queued to Redis (non-blocking)
      4. HTTP 302 response
    """

    def __init__(
        self,
        session: AsyncSession,
        url_cache: URLCache,
        analytics_cache: AnalyticsCache,
    ) -> None:
        self._repo = URLRepository(session)
        self._url_cache = url_cache
        self._analytics_cache = analytics_cache

    async def resolve(
        self,
        code: str,
        *,
        background_tasks: BackgroundTasks,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        referrer: Optional[str] = None,
    ) -> str:
        cached = await self._url_cache.get(code)

        if cached:
            self._guard_expiry(cached)
            url_id = uuid.UUID(cached["id"])
            original_url = cached["original_url"]
        else:
            db_url = await self._repo.get_active_by_code(code)
            if not db_url:
                raise URLNotFoundError()

            original_url = db_url.original_url
            url_id = db_url.id

            # Warm the cache on the way out
            background_tasks.add_task(
                self._url_cache.set,
                code,
                {
                    "id": str(db_url.id),
                    "original_url": original_url,
                    "short_code": db_url.short_code,
                    "custom_alias": db_url.custom_alias,
                    "is_active": db_url.is_active,
                    "expires_at": db_url.expires_at.isoformat() if db_url.expires_at else None,
                },
            )
            logger.info("url_cache_warmed", code=code)

        # Track click frequency for hot-URL detection
        background_tasks.add_task(self._url_cache.track_click, code)

        # Queue analytics event — never blocks the redirect response
        background_tasks.add_task(
            self._enqueue_click,
            url_id=url_id,
            ip_address=ip_address,
            user_agent=user_agent,
            referrer=referrer,
        )

        return original_url

    async def _enqueue_click(
        self,
        url_id: uuid.UUID,
        ip_address: Optional[str],
        user_agent: Optional[str],
        referrer: Optional[str],
    ) -> None:
        try:
            parsed_ua = parse_user_agent(user_agent)
            event = ClickEvent(
                short_url_id=url_id,
                ip_address=ip_address,
                user_agent=user_agent,
                referrer=referrer,
                browser=parsed_ua.browser,
                os=parsed_ua.os,
                device=parsed_ua.device,
            )
            await self._analytics_cache.push_event(event.to_dict())
        except Exception as exc:
            logger.error("analytics_enqueue_error", error=str(exc), url_id=str(url_id))

    @staticmethod
    def _guard_expiry(cached: dict) -> None:
        expires_at = cached.get("expires_at")
        if expires_at:
            expiry = datetime.fromisoformat(expires_at)
            if expiry <= datetime.now(timezone.utc):
                raise URLExpiredError()
