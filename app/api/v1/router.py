from fastapi import APIRouter

from app.api.v1.endpoints import analytics, auth, health, qr, urls

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(urls.router)
api_router.include_router(analytics.router)
api_router.include_router(qr.router)
api_router.include_router(health.router)
