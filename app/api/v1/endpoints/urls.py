from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import Response

from app.dependencies.auth import CurrentUser, OptionalUser
from app.dependencies.cache import RateLimiterDep, URLCacheDep
from app.dependencies.db import DBSession
from app.schemas.url import URLCreateRequest, URLListResponse, URLResponse, URLUpdateRequest
from app.services.url import URLService

router = APIRouter(prefix="/urls", tags=["URLs"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else "unknown"
    )


@router.post("", response_model=URLResponse, status_code=status.HTTP_201_CREATED)
async def create_url(
    data: URLCreateRequest,
    request: Request,
    session: DBSession,
    url_cache: URLCacheDep,
    rate_limiter: RateLimiterDep,
    user: OptionalUser,
) -> URLResponse:
    identifier = str(user.id) if user else _client_ip(request)
    limit = 100 if user else 10
    allowed, _, _ = await rate_limiter.is_allowed(identifier, limit=limit, window=3600, endpoint="create_url")
    if not allowed:
        from app.core.exceptions import RateLimitError
        raise RateLimitError("URL creation rate limit exceeded")

    svc = URLService(session, url_cache)
    return await svc.create(data, owner_id=user.id if user else None)


@router.get("", response_model=URLListResponse)
async def list_urls(
    session: DBSession,
    url_cache: URLCacheDep,
    user: CurrentUser,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> URLListResponse:
    return await URLService(session, url_cache).list_by_owner(user.id, page=page, size=size)


@router.get("/{url_id}", response_model=URLResponse)
async def get_url(
    url_id: uuid.UUID,
    session: DBSession,
    url_cache: URLCacheDep,
    user: OptionalUser,
) -> URLResponse:
    requester_id = user.id if user else None
    return await URLService(session, url_cache).get_by_id(url_id, requester_id=requester_id)


@router.patch("/{url_id}", response_model=URLResponse)
async def update_url(
    url_id: uuid.UUID,
    data: URLUpdateRequest,
    session: DBSession,
    url_cache: URLCacheDep,
    user: CurrentUser,
) -> URLResponse:
    is_admin = user.role == "admin"
    return await URLService(session, url_cache).update(url_id, data, user.id, is_admin=is_admin)


@router.delete("/{url_id}")
async def delete_url(
    url_id: uuid.UUID,
    session: DBSession,
    url_cache: URLCacheDep,
    user: CurrentUser,
) -> Response:
    is_admin = user.role == "admin"
    await URLService(session, url_cache).delete(url_id, user.id, is_admin=is_admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
