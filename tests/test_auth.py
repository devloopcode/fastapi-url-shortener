from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_user, get_auth_headers

pytestmark = pytest.mark.asyncio


async def test_register_success(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "StrongPass1", "full_name": "New User"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "new@example.com"
    assert "hashed_password" not in data


async def test_register_duplicate_email(client: AsyncClient):
    await create_test_user(client, "dup@example.com")
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": "StrongPass1"},
    )
    assert resp.status_code == 409


async def test_register_weak_password(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "weak@example.com", "password": "password"},
    )
    assert resp.status_code == 422


async def test_login_success(client: AsyncClient):
    await create_test_user(client, "login@example.com")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "TestPass1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient):
    await create_test_user(client, "wrongpw@example.com")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@example.com", "password": "WrongPass1"},
    )
    assert resp.status_code == 401


async def test_me_endpoint(client: AsyncClient):
    await create_test_user(client, "me@example.com")
    headers = await get_auth_headers(client, "me@example.com")
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


async def test_me_without_token(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
