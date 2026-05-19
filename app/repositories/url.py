from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import func, or_, select, update

from app.models.short_url import ShortURL
from app.repositories.base import BaseRepository


class URLRepository(BaseRepository[ShortURL]):
    model = ShortURL

    async def get_by_short_code(self, short_code: str) -> Optional[ShortURL]:
        result = await self.session.execute(
            select(ShortURL).where(ShortURL.short_code == short_code)
        )
        return result.scalar_one_or_none()

    async def get_by_alias(self, alias: str) -> Optional[ShortURL]:
        result = await self.session.execute(
            select(ShortURL).where(ShortURL.custom_alias == alias)
        )
        return result.scalar_one_or_none()

    async def short_code_exists(self, short_code: str) -> bool:
        result = await self.session.execute(
            select(ShortURL.id).where(
                or_(ShortURL.short_code == short_code, ShortURL.custom_alias == short_code)
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_active_by_code(self, code: str) -> Optional[ShortURL]:
        """Return a URL only if it is active and not expired."""
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(ShortURL).where(
                or_(ShortURL.short_code == code, ShortURL.custom_alias == code),
                ShortURL.is_active.is_(True),
                or_(ShortURL.expires_at.is_(None), ShortURL.expires_at > now),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_owner(
        self,
        owner_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[ShortURL], int]:
        count_result = await self.session.execute(
            select(func.count()).select_from(ShortURL).where(ShortURL.owner_id == owner_id)
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            select(ShortURL)
            .where(ShortURL.owner_id == owner_id)
            .order_by(ShortURL.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all(), total

    async def increment_click_count(self, url_id: uuid.UUID) -> None:
        await self.session.execute(
            update(ShortURL)
            .where(ShortURL.id == url_id)
            .values(click_count=ShortURL.click_count + 1)
        )
