from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_user, get_auth_headers

pytestmark = pytest.mark.asyncio


async def test_redirect_from_cache(client: AsyncClient, mock_redis):
    url_id = str(uuid.uuid4())
    cached_payload = json.dumps({
        "id": url_id,
        "original_url": "https://cached-destination.com",
        "short_code": "cached1",
        "custom_alias": None,
        "is_active": True,
        "expires_at": None,
    })
    mock_redis.get = AsyncMock(return_value=cached_payload)

    resp = await client.get("/cached1", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://cached-destination.com"


async def test_redirect_not_found(client: AsyncClient, mock_redis):
    mock_redis.get = AsyncMock(return_value=None)
    resp = await client.get("/nonexistent99", follow_redirects=False)
    assert resp.status_code == 404


async def test_redirect_via_db(client: AsyncClient, mock_redis):
    """Cache miss falls back to DB; result is queued for warming via BackgroundTasks."""
    mock_redis.get = AsyncMock(return_value=None)

    await create_test_user(client, "redir@example.com")
    headers = await get_auth_headers(client, "redir@example.com")
    create_resp = await client.post(
        "/api/v1/urls",
        json={"original_url": "https://real-destination.com"},
        headers=headers,
    )
    short_code = create_resp.json()["short_code"]

    resp = await client.get(f"/{short_code}", follow_redirects=False)
    assert resp.status_code == 302
    assert "real-destination.com" in resp.headers["location"]


async def test_redirect_expired_url(client: AsyncClient, mock_redis):
    """Cache hit for an expired URL should return 410 Gone."""
    url_id = str(uuid.uuid4())
    cached_payload = json.dumps({
        "id": url_id,
        "original_url": "https://expired.com",
        "short_code": "expired1",
        "custom_alias": None,
        "is_active": True,
        "expires_at": "2020-01-01T00:00:00+00:00",  # past date
    })
    mock_redis.get = AsyncMock(return_value=cached_payload)

    resp = await client.get("/expired1", follow_redirects=False)
    assert resp.status_code == 410
