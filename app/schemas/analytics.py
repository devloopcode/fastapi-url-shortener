from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel


class ClickEventData(BaseModel):
    short_url_id: uuid.UUID
    visitor_hash: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    referrer: Optional[str] = None
    user_agent: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    device: Optional[str] = None


class DimensionBreakdown(BaseModel):
    label: str
    count: int
    percentage: float


class DailyClickStat(BaseModel):
    date: date
    clicks: int
    unique_visitors: int


class AnalyticsSummary(BaseModel):
    short_code: str
    total_clicks: int
    unique_visitors: int
    top_countries: list[DimensionBreakdown]
    top_browsers: list[DimensionBreakdown]
    top_os: list[DimensionBreakdown]
    top_devices: list[DimensionBreakdown]
    top_referrers: list[DimensionBreakdown]
    daily_stats: list[DailyClickStat]
    period_days: int


class AnalyticsDetailResponse(BaseModel):
    short_url_id: uuid.UUID
    short_code: str
    snapshot_date: date
    total_clicks: int
    unique_visitors: int
    country_data: dict[str, Any]
    browser_data: dict[str, Any]
    os_data: dict[str, Any]
    device_data: dict[str, Any]
    referrer_data: dict[str, Any]

    model_config = {"from_attributes": True}
