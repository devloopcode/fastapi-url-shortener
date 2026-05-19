from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.analytics_cache import AnalyticsCache
from app.core.exceptions import NotFoundError
from app.models.click_event import ClickEvent
from app.repositories.analytics import AnalyticsRepository
from app.repositories.click_event import ClickEventRepository
from app.repositories.url import URLRepository
from app.schemas.analytics import (
    AnalyticsSummary,
    DailyClickStat,
    DimensionBreakdown,
)


class AnalyticsService:
    def __init__(self, session: AsyncSession, cache: AnalyticsCache) -> None:
        self._repo = AnalyticsRepository(session)
        self._clicks = ClickEventRepository(session)
        self._urls = URLRepository(session)
        self._cache = cache

    async def get_summary(
        self, short_code: str, *, days: int = 30
    ) -> AnalyticsSummary:
        cached = await self._cache.get_summary(short_code)
        if cached:
            return AnalyticsSummary(**cached)

        url = await self._urls.get_by_short_code(short_code)
        if not url:
            raise NotFoundError("Short URL")

        since = datetime.now(timezone.utc) - timedelta(days=days)

        total_clicks = url.click_count
        unique_visitors = await self._clicks.count_unique_visitors(url.id, since=since)

        countries = await self._clicks.get_dimension_counts(url.id, ClickEvent.country, since=since)
        browsers = await self._clicks.get_dimension_counts(url.id, ClickEvent.browser, since=since)
        os_list = await self._clicks.get_dimension_counts(url.id, ClickEvent.os, since=since)
        devices = await self._clicks.get_dimension_counts(url.id, ClickEvent.device, since=since)
        referrers = await self._clicks.get_dimension_counts(url.id, ClickEvent.referrer, since=since)

        daily_raw = await self._clicks.get_daily_stats(url.id, days=days)

        def to_breakdown(rows: list, total: int) -> list[DimensionBreakdown]:
            return [
                DimensionBreakdown(
                    label=str(r[0]),
                    count=r[1],
                    percentage=round(r[1] / total * 100, 1) if total else 0,
                )
                for r in rows
            ]

        summary = AnalyticsSummary(
            short_code=short_code,
            total_clicks=total_clicks,
            unique_visitors=unique_visitors,
            top_countries=to_breakdown(countries, total_clicks),
            top_browsers=to_breakdown(browsers, total_clicks),
            top_os=to_breakdown(os_list, total_clicks),
            top_devices=to_breakdown(devices, total_clicks),
            top_referrers=to_breakdown(referrers, total_clicks),
            daily_stats=[
                DailyClickStat(date=r[0], clicks=r[1], unique_visitors=r[2])
                for r in daily_raw
            ],
            period_days=days,
        )

        await self._cache.set_summary(short_code, summary.model_dump(mode="json"))
        return summary
