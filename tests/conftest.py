from __future__ import annotations

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db_session
from app.cache.client import get_redis
from app.main import app as main_app

# SQLite for fast unit tests. For DB-specific behaviour (UUID columns,
# JSON operators, RETURNING, etc.) add a parallel integration test suite
# that targets a real PostgreSQL instance (see tests/integration/).
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.rpush = AsyncMock(return_value=1)
    redis.llen = AsyncMock(return_value=0)
    redis.lmpop = AsyncMock(return_value=None)
    redis.ping = AsyncMock(return_value=True)
    redis.pipeline = MagicMock(return_value=AsyncMock())
    redis.evalsha = AsyncMock(return_value=[1, 99, 60])
    return redis


@pytest_asyncio.fixture
async def client(db_session, mock_redis) -> AsyncGenerator[AsyncClient, None]:
    app = main_app

    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: mock_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Test helpers ──────────────────────────────────────────────────────────────

async def create_test_user(client: AsyncClient, email: str = "test@example.com") -> dict:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "TestPass1", "full_name": "Test User"},
    )
    assert resp.status_code == 201
    return resp.json()


async def get_auth_headers(client: AsyncClient, email: str = "test@example.com") -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "TestPass1"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
