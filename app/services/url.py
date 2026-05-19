from __future__ import annotations

import math
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.url_cache import URLCache
from app.config import settings
from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ShortCodeCollisionError,
    ValidationError,
)
from app.models.short_url import ShortURL
from app.models.user import UserRole
from app.repositories.url import URLRepository
from app.schemas.url import URLCreateRequest, URLListResponse, URLResponse, URLUpdateRequest
from app.utils.short_code import generate_short_code
from app.utils.url_validator import is_safe_url


def _to_response(url: ShortURL) -> URLResponse:
    return URLResponse(
        id=url.id,
        original_url=url.original_url,
        short_code=url.short_code,
        custom_alias=url.custom_alias,
        title=url.title,
        short_url=f"{settings.BASE_URL}/{url.custom_alias or url.short_code}",
        owner_id=url.owner_id,
        is_active=url.is_active,
        is_public=url.is_public,
        expires_at=url.expires_at,
        click_count=url.click_count,
        created_at=url.created_at,
        updated_at=url.updated_at,
    )


class URLService:
    def __init__(self, session: AsyncSession, url_cache: URLCache) -> None:
        self._repo = URLRepository(session)
        self._cache = url_cache

    async def create(
        self,
        data: URLCreateRequest,
        owner_id: Optional[uuid.UUID] = None,
    ) -> URLResponse:
        original = str(data.original_url)

        if not is_safe_url(original):
            raise ValidationError("URL is not allowed (blocked host or scheme)")

        if data.custom_alias:
            if await self._repo.short_code_exists(data.custom_alias):
                raise ConflictError(f"Alias '{data.custom_alias}' is already taken")
            short_code = data.custom_alias
        else:
            short_code = await self._generate_unique_code()

        url = await self._repo.create(
            original_url=original,
            short_code=short_code,
            custom_alias=data.custom_alias,
            title=data.title,
            owner_id=owner_id,
            is_public=data.is_public,
            expires_at=data.expires_at,
        )

        await self._cache.set(short_code, self._serialize(url))
        return _to_response(url)

    async def get_by_id(
        self, url_id: uuid.UUID, requester_id: Optional[uuid.UUID] = None
    ) -> URLResponse:
        url = await self._repo.get_by_id(url_id)
        if not url:
            raise NotFoundError("URL")

        if not url.is_public and url.owner_id != requester_id:
            raise AuthorizationError("This link is private")

        return _to_response(url)

    async def list_by_owner(
        self,
        owner_id: uuid.UUID,
        page: int = 1,
        size: int = 20,
    ) -> URLListResponse:
        offset = (page - 1) * size
        urls, total = await self._repo.get_by_owner(owner_id, offset=offset, limit=size)
        return URLListResponse(
            items=[_to_response(u) for u in urls],
            total=total,
            page=page,
            size=size,
            pages=math.ceil(total / size) if total else 0,
        )

    async def update(
        self,
        url_id: uuid.UUID,
        data: URLUpdateRequest,
        requester_id: uuid.UUID,
        is_admin: bool = False,
    ) -> URLResponse:
        url = await self._repo.get_by_id(url_id)
        if not url:
            raise NotFoundError("URL")

        if not is_admin and url.owner_id != requester_id:
            raise AuthorizationError("You don't own this link")

        updates = data.model_dump(exclude_none=True)
        url = await self._repo.update(url, **updates)

        # Invalidate cache so the updated data is served immediately
        await self._cache.delete(url.short_code)
        if url.custom_alias:
            await self._cache.delete(url.custom_alias)

        return _to_response(url)

    async def delete(
        self,
        url_id: uuid.UUID,
        requester_id: uuid.UUID,
        is_admin: bool = False,
    ) -> None:
        url = await self._repo.get_by_id(url_id)
        if not url:
            raise NotFoundError("URL")

        if not is_admin and url.owner_id != requester_id:
            raise AuthorizationError("You don't own this link")

        await self._cache.delete(url.short_code)
        if url.custom_alias:
            await self._cache.delete(url.custom_alias)

        await self._repo.delete(url)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _generate_unique_code(self) -> str:
        for _ in range(settings.MAX_COLLISION_RETRIES):
            code = generate_short_code()
            if not await self._repo.short_code_exists(code):
                return code
        raise ShortCodeCollisionError()

    @staticmethod
    def _serialize(url: ShortURL) -> dict:
        return {
            "id": str(url.id),
            "original_url": url.original_url,
            "short_code": url.short_code,
            "custom_alias": url.custom_alias,
            "is_active": url.is_active,
            "expires_at": url.expires_at.isoformat() if url.expires_at else None,
        }
