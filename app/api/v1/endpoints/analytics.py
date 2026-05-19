from __future__ import annotations

from fastapi import APIRouter, Query

from app.dependencies.auth import CurrentUser
from app.dependencies.cache import AnalyticsCacheDep
from app.dependencies.db import DBSession
from app.schemas.analytics import AnalyticsSummary
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/{short_code}/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    short_code: str,
    session: DBSession,
    cache: AnalyticsCacheDep,
    user: CurrentUser,
    days: int = Query(default=30, ge=1, le=365),
) -> AnalyticsSummary:
    return await AnalyticsService(session, cache).get_summary(short_code, days=days)
