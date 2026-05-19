from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_rate_limiter_allows_within_limit(client: AsyncClient):
    """Smoke test: registration endpoint should succeed on first attempt."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "ratelimit@example.com", "password": "TestPass1"},
    )
    # Either created or already exists — both mean the request was not rate-limited (429)
    assert resp.status_code != 429


async def test_health_endpoint_not_rate_limited(client: AsyncClient):
    for _ in range(5):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200


async def test_rate_limiter_blocks_excess_requests(mock_redis):
    """Sliding window limiter should return False once the window is exhausted."""
    from app.cache.rate_limiter import SlidingWindowRateLimiter

    # Simulate a window already at capacity: evalsha returns [0, 0, reset_after]
    mock_redis.evalsha = AsyncMock(return_value=[0, 0, 60])
    mock_redis.script_load = AsyncMock(return_value="abc123")

    limiter = SlidingWindowRateLimiter(mock_redis)
    # Prime the script SHA so the limiter can call evalsha
    limiter._script_sha = "abc123"

    allowed, remaining, reset = await limiter.is_allowed(
        "test-identifier", limit=10, window=60, endpoint="test"
    )
    assert allowed is False
    assert remaining == 0
    assert reset > 0


async def test_rate_limiter_allows_when_under_limit(mock_redis):
    """Limiter should return True and decrement remaining when under limit."""
    from app.cache.rate_limiter import SlidingWindowRateLimiter

    # evalsha returns [1, remaining=9, window=60]
    mock_redis.evalsha = AsyncMock(return_value=[1, 9, 60])
    mock_redis.script_load = AsyncMock(return_value="abc123")

    limiter = SlidingWindowRateLimiter(mock_redis)
    limiter._script_sha = "abc123"

    allowed, remaining, _ = await limiter.is_allowed(
        "test-identifier", limit=10, window=60, endpoint="test"
    )
    assert allowed is True
    assert remaining == 9
