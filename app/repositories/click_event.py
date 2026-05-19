from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Sequence

from sqlalchemy import func, select

from app.models.click_event import ClickEvent
from app.repositories.base import BaseRepository


class ClickEventRepository(BaseRepository[ClickEvent]):
    model = ClickEvent

    async def bulk_insert(self, events: list[dict[str, Any]]) -> None:
        instances = [ClickEvent(**e) for e in events]
        self.session.add_all(instances)
        await self.session.flush()

    async def get_by_url(
        self,
        short_url_id: uuid.UUID,
        *,
        since: datetime | None = None,
        limit: int = 1000,
    ) -> Sequence[ClickEvent]:
        stmt = select(ClickEvent).where(ClickEvent.short_url_id == short_url_id)
        if since:
            stmt = stmt.where(ClickEvent.created_at >= since)
        stmt = stmt.order_by(ClickEvent.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_unique_visitors(
        self, short_url_id: uuid.UUID, since: datetime | None = None
    ) -> int:
        stmt = (
            select(func.count(func.distinct(ClickEvent.visitor_hash)))
            .where(ClickEvent.short_url_id == short_url_id)
            .where(ClickEvent.visitor_hash.isnot(None))
        )
        if since:
            stmt = stmt.where(ClickEvent.created_at >= since)
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def get_dimension_counts(
        self,
        short_url_id: uuid.UUID,
        dimension_col: Any,
        since: datetime | None = None,
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        stmt = (
            select(dimension_col, func.count().label("cnt"))
            .where(ClickEvent.short_url_id == short_url_id)
            .where(dimension_col.isnot(None))
            .group_by(dimension_col)
            .order_by(func.count().desc())
            .limit(limit)
        )
        if since:
            stmt = stmt.where(ClickEvent.created_at >= since)
        result = await self.session.execute(stmt)
        return result.all()

    async def get_daily_stats(
        self,
        short_url_id: uuid.UUID,
        days: int = 30,
    ) -> list[tuple[date, int, int]]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(
                func.date(ClickEvent.created_at).label("day"),
                func.count().label("total"),
                func.count(func.distinct(ClickEvent.visitor_hash)).label("unique"),
            )
            .where(ClickEvent.short_url_id == short_url_id)
            .where(ClickEvent.created_at >= since)
            .group_by(func.date(ClickEvent.created_at))
            .order_by(func.date(ClickEvent.created_at))
        )
        result = await self.session.execute(stmt)
        return result.all()
