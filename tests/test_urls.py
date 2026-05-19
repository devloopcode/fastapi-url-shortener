from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_user, get_auth_headers

pytestmark = pytest.mark.asyncio


async def test_create_url_authenticated(client: AsyncClient):
    await create_test_user(client, "url@example.com")
    headers = await get_auth_headers(client, "url@example.com")
    resp = await client.post(
        "/api/v1/urls",
        json={"original_url": "https://example.com/long-path"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["original_url"] == "https://example.com/long-path"
    assert len(data["short_code"]) == 7
    assert "short_url" in data


async def test_create_url_with_custom_alias(client: AsyncClient):
    await create_test_user(client, "alias@example.com")
    headers = await get_auth_headers(client, "alias@example.com")
    resp = await client.post(
        "/api/v1/urls",
        json={"original_url": "https://example.com", "custom_alias": "myalias"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["custom_alias"] == "myalias"


async def test_create_url_duplicate_alias(client: AsyncClient):
    await create_test_user(client, "dups@example.com")
    headers = await get_auth_headers(client, "dups@example.com")
    payload = {"original_url": "https://example.com", "custom_alias": "taken"}
    await client.post("/api/v1/urls", json=payload, headers=headers)
    resp = await client.post("/api/v1/urls", json=payload, headers=headers)
    assert resp.status_code == 409


async def test_create_url_rejects_localhost(client: AsyncClient):
    await create_test_user(client, "ssrf@example.com")
    headers = await get_auth_headers(client, "ssrf@example.com")
    resp = await client.post(
        "/api/v1/urls",
        json={"original_url": "http://localhost/admin"},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_create_url_rejects_private_range(client: AsyncClient):
    await create_test_user(client, "ssrf2@example.com")
    headers = await get_auth_headers(client, "ssrf2@example.com")
    for url in [
        "http://192.168.1.1/secret",
        "http://10.0.0.1/internal",
        "http://172.16.0.1/api",
    ]:
        resp = await client.post("/api/v1/urls", json={"original_url": url}, headers=headers)
        assert resp.status_code == 422, f"Expected 422 for SSRF target {url}"


async def test_list_urls(client: AsyncClient):
    await create_test_user(client, "list@example.com")
    headers = await get_auth_headers(client, "list@example.com")
    await client.post("/api/v1/urls", json={"original_url": "https://a.com"}, headers=headers)
    await client.post("/api/v1/urls", json={"original_url": "https://b.com"}, headers=headers)
    resp = await client.get("/api/v1/urls", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 2


async def test_delete_url(client: AsyncClient):
    await create_test_user(client, "del@example.com")
    headers = await get_auth_headers(client, "del@example.com")
    create_resp = await client.post(
        "/api/v1/urls",
        json={"original_url": "https://todelete.com"},
        headers=headers,
    )
    url_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/urls/{url_id}", headers=headers)
    assert resp.status_code == 204


async def test_delete_url_unauthorized(client: AsyncClient):
    await create_test_user(client, "owner@example.com")
    await create_test_user(client, "other@example.com")
    owner_headers = await get_auth_headers(client, "owner@example.com")
    other_headers = await get_auth_headers(client, "other@example.com")
    create_resp = await client.post(
        "/api/v1/urls",
        json={"original_url": "https://private.com"},
        headers=owner_headers,
    )
    url_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/urls/{url_id}", headers=other_headers)
    assert resp.status_code == 403
