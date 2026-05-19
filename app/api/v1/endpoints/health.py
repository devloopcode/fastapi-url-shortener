from __future__ import annotations

from fastapi import APIRouter
# pyrefly: ignore [missing-import]
from sqlalchemy import text

from app.cache.client import get_redis
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import AsyncSessionFactory

router = APIRouter(tags=["Health"])
logger = get_logger(__name__)


@router.get("/health", summary="Health check")
async def health() -> dict:
    status: dict[str, str] = {"api": "ok", "database": "unknown", "redis": "unknown"}

    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception as exc:
        logger.error("health_check_db_failure", error=str(exc))
        # Expose details only in non-production to avoid leaking connection strings
        status["database"] = f"error: {exc}" if settings.DEBUG else "error"

    try:
        redis = await get_redis()
        await redis.ping()
        status["redis"] = "ok"
    except Exception as exc:
        logger.error("health_check_redis_failure", error=str(exc))
        status["redis"] = f"error: {exc}" if settings.DEBUG else "error"

    return status
