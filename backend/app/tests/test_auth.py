import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "mcinnes@dmp.co.nz",
        "password": "securepassword123",
        "first_name": "Mcinnes",
        "last_name": "Taljaard",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "mcinnes@dmp.co.nz"
    assert data["first_name"] == "Mcinnes"
    assert data["last_name"] == "Taljaard"
    assert "id" in data


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "mcinnes@dmp.co.nz",
        "password": "securepassword123",
        "first_name": "Mcinnes",
        "last_name": "Taljaard",
    })
    resp = await client.post("/api/v1/auth/login", data={
        "username": "mcinnes@dmp.co.nz",
        "password": "securepassword123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_protected_route(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
