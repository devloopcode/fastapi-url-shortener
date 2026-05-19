from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse, RedirectResponse
# pyrefly: ignore [missing-import]
from fastapi.background import BackgroundTasks

from app.api.v1.router import api_router
from app.cache.analytics_cache import AnalyticsCache
from app.cache.client import close_redis, get_redis
from app.cache.url_cache import URLCache
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import configure_logging, get_logger
from app.db.session import AsyncSessionFactory, engine
from app.middleware.logging import RequestLoggingMiddleware
from app.services.redirect import RedirectService
from app.tasks.analytics_tasks import start_analytics_worker, stop_analytics_worker

configure_logging(debug=settings.DEBUG)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("startup", env=settings.ENVIRONMENT, version=settings.APP_VERSION)

    redis = await get_redis()
    analytics_cache = AnalyticsCache(redis)
    await start_analytics_worker(analytics_cache)

    yield

    await stop_analytics_worker()
    await close_redis()
    await engine.dispose()
    logger.info("shutdown_complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.ALLOWED_METHODS,
    allow_headers=settings.ALLOWED_HEADERS,
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(api_router)


# ── Exception handlers ────────────────────────────────────────────────────────

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.message, "data": None},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.detail, "data": None},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error", "data": None},
    )


# ── Redirect endpoint (critical path — kept outside the versioned router) ─────

@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/{short_code}", include_in_schema=False)
async def redirect(
    short_code: str,
    request: Request,
    background_tasks: BackgroundTasks,
) -> RedirectResponse:
    """
    The hot path. Resolution order:
      1. Redis cache
      2. PostgreSQL (result written back to cache via background task)
      3. Async analytics event queued — never blocks the response
    """
    # Skip API and static paths accidentally routed here
    if short_code in ("docs", "redoc", "openapi.json", "health", "favicon.ico"):
        raise HTTPException(status_code=404)

    redis = await get_redis()
    url_cache = URLCache(redis)
    analytics_cache = AnalyticsCache(redis)

    async with AsyncSessionFactory() as session:
        svc = RedirectService(session, url_cache, analytics_cache)

        ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
            request.client.host if request.client else None
        )

        original_url = await svc.resolve(
            short_code,
            background_tasks=background_tasks,
            ip_address=ip,
            user_agent=request.headers.get("User-Agent"),
            referrer=request.headers.get("Referer"),
        )

    return RedirectResponse(url=original_url, status_code=status.HTTP_302_FOUND)
