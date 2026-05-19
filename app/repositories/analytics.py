from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Sequence

from sqlalchemy import select

from app.models.analytics_snapshot import AnalyticsSnapshot
from app.repositories.base import BaseRepository


class AnalyticsRepository(BaseRepository[AnalyticsSnapshot]):
    model = AnalyticsSnapshot

    async def get_by_url_and_date(
        self, short_url_id: uuid.UUID, snapshot_date: date
    ) -> AnalyticsSnapshot | None:
        result = await self.session.execute(
            select(AnalyticsSnapshot).where(
                AnalyticsSnapshot.short_url_id == short_url_id,
                AnalyticsSnapshot.snapshot_date == snapshot_date,
            )
        )
        return result.scalar_one_or_none()

    async def get_range(
        self,
        short_url_id: uuid.UUID,
        days: int = 30,
    ) -> Sequence[AnalyticsSnapshot]:
        since = date.today() - timedelta(days=days)
        result = await self.session.execute(
            select(AnalyticsSnapshot)
            .where(
                AnalyticsSnapshot.short_url_id == short_url_id,
                AnalyticsSnapshot.snapshot_date >= since,
            )
            .order_by(AnalyticsSnapshot.snapshot_date)
        )
        return result.scalars().all()

    async def upsert(self, short_url_id: uuid.UUID, snapshot_date: date, **kwargs) -> AnalyticsSnapshot:
        snapshot = await self.get_by_url_and_date(short_url_id, snapshot_date)
        if snapshot:
            return await self.update(snapshot, **kwargs)
        return await self.create(
            short_url_id=short_url_id, snapshot_date=snapshot_date, **kwargs
        )
