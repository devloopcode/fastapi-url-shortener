from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_rate_limiter_allows_within_limit(client: AsyncClient):
    """Smoke test: registration endpoint should succeed on first attempt."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "ratelimit@example.com", "password": "TestPass1"},
    )
    # Either created or already exists — both mean we weren't rate-limited (429)
    assert resp.status_code != 429


async def test_health_endpoint_not_rate_limited(client: AsyncClient):
    for _ in range(5):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
