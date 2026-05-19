from __future__ import annotations

from fastapi import APIRouter, Request, status
# pyrefly: ignore [missing-import]
from fastapi.responses import Response

from app.dependencies.auth import CurrentUser
from app.dependencies.cache import RateLimiterDep
from app.dependencies.db import DBSession
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    request: Request,
    session: DBSession,
    rate_limiter: RateLimiterDep,
) -> UserResponse:
    ip = _get_client_ip(request)
    allowed, _, _ = await rate_limiter.is_allowed(
        ip or "anon", limit=10, window=3600, endpoint="register"
    )
    if not allowed:
        from app.core.exceptions import RateLimitError
        raise RateLimitError("Too many registration attempts")

    svc = AuthService(session)
    user = await svc.register(data, ip=ip)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    request: Request,
    session: DBSession,
    rate_limiter: RateLimiterDep,
) -> TokenResponse:
    ip = _get_client_ip(request)
    allowed, _, _ = await rate_limiter.is_allowed(
        ip or "anon", limit=20, window=300, endpoint="login"
    )
    if not allowed:
        from app.core.exceptions import RateLimitError
        raise RateLimitError("Too many login attempts")

    svc = AuthService(session)
    return await svc.login(data, ip=ip, user_agent=request.headers.get("User-Agent"))


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshRequest, session: DBSession) -> TokenResponse:
    return await AuthService(session).refresh(data.refresh_token)


@router.post("/logout")
async def logout(data: RefreshRequest, session: DBSession) -> Response:
    await AuthService(session).logout(data.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
