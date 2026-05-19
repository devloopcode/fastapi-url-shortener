from __future__ import annotations

import base64
import io

import qrcode
from qrcode.image.pil import PilImage
from redis.asyncio import Redis

from app.config import settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.repositories.url import URLRepository
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

_QR_PREFIX = "qr:"


class QRService:
    """
    Generates QR codes for short URLs and caches them in Redis.

    QR images are returned as base64-encoded PNG so consumers can embed
    them directly in HTML <img> tags or save them as files.
    """

    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._repo = URLRepository(session)
        self._redis = redis

    async def get_or_generate(self, short_code: str) -> bytes:
        """Return cached PNG bytes, generating and caching on first call."""
        cache_key = f"{_QR_PREFIX}{short_code}"

        cached = await self._redis.get(cache_key)
        if cached:
            logger.debug("qr_cache_hit", short_code=short_code)
            return base64.b64decode(cached)

        # Validate the short code exists
        url = await self._repo.get_by_short_code(short_code)
        if not url:
            raise NotFoundError("Short URL")

        target = f"{settings.BASE_URL}/{url.custom_alias or url.short_code}"
        png_bytes = self._render(target)

        # Cache as base64 string (Redis stores strings)
        await self._redis.setex(
            cache_key,
            settings.QR_CACHE_TTL,
            base64.b64encode(png_bytes).decode(),
        )
        logger.info("qr_generated", short_code=short_code)
        return png_bytes

    async def invalidate(self, short_code: str) -> None:
        await self._redis.delete(f"{_QR_PREFIX}{short_code}")

    @staticmethod
    def _render(url: str) -> bytes:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img: PilImage = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
