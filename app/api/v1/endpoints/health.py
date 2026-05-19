from __future__ import annotations

from fastapi import APIRouter
# pyrefly: ignore [missing-import]
from sqlalchemy import text

from app.cache.client import get_redis
from app.db.session import AsyncSessionFactory

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health check")
async def health() -> dict:
    status = {"api": "ok", "database": "unknown", "redis": "unknown"}

    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception as exc:
        status["database"] = f"error: {exc}"

    try:
        redis = await get_redis()
        await redis.ping()
        status["redis"] = "ok"
    except Exception as exc:
        status["redis"] = f"error: {exc}"

    return status
