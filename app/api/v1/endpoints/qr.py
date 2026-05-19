from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from app.dependencies.cache import RedisClient
from app.dependencies.db import DBSession
from app.services.qr import QRService

router = APIRouter(prefix="/qr", tags=["QR Codes"])


@router.get("/{short_code}", response_class=Response)
async def get_qr_code(
    short_code: str,
    session: DBSession,
    redis: RedisClient,
) -> Response:
    """Returns a downloadable PNG QR code for the given short code."""
    svc = QRService(session, redis)
    png_bytes = await svc.get_or_generate(short_code)
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{short_code}.png"'},
    )
