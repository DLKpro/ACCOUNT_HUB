"""Integration tests for auth API endpoints.

These tests exercise the full stack: HTTP routes → service layer → security
modules (hashing, JWT, encryption) → database models → SQLite test DB.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "newuser", "email": "newuser@test.com",
        "password": "strongpassword",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_invalid_username(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "ab", "email": "ab@test.com",  # too short
        "password": "testpass1",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    await client.post("/auth/register", json={
        "username": "dupeuser", "email": "dupeuser@test.com",
        "password": "testpass1",
    })
    resp = await client.post("/auth/register", json={
        "username": "dupeuser", "email": "dupeuser2@test.com",
        "password": "testpass2",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    # Register first
    await client.post("/auth/register", json={
        "username": "loginuser", "email": "loginuser@test.com",
        "password": "mypassword",
    })
    # Then login
    resp = await client.post("/auth/login", json={
        "username": "loginuser",
        "password": "mypassword",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/auth/register", json={
        "username": "wrongpwuser", "email": "wrongpwuser@test.com",
        "password": "correctpass",
    })
    resp = await client.post("/auth/login", json={
        "username": "wrongpwuser",
        "password": "wrongpass1",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    resp = await client.post("/auth/login", json={
        "username": "nobody_here",
        "password": "anything1",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_token(client: AsyncClient):
    reg = await client.post("/auth/register", json={
        "username": "meuser", "email": "meuser@test.com",
        "password": "testpass1",
    })
    token = reg.json()["access_token"]
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "meuser"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code in (401, 403)  # HTTPBearer returns 401 or 403 depending on version


@pytest.mark.asyncio
async def test_me_with_invalid_token(client: AsyncClient):
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer garbage-token"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_returns_new_tokens(client: AsyncClient):
    reg = await client.post("/auth/register", json={
        "username": "refreshuser", "email": "refreshuser@test.com",
        "password": "testpass1",
    })
    refresh_token = reg.json()["refresh_token"]

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # New tokens should work
    me_resp = await client.get("/auth/me", headers={
        "Authorization": f"Bearer {data['access_token']}"
    })
    assert me_resp.status_code == 200


@pytest.mark.asyncio
async def test_refresh_with_access_token_fails(client: AsyncClient):
    reg = await client.post("/auth/register", json={
        "username": "badrefreshuser", "email": "badrefreshuser@test.com",
        "password": "testpass1",
    })
    access_token = reg.json()["access_token"]
    resp = await client.post("/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_garbage_fails(client: AsyncClient):
    resp = await client.post("/auth/refresh", json={"refresh_token": "not-valid"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_account(client: AsyncClient):
    reg = await client.post("/auth/register", json={
        "username": "deleteuser", "email": "deleteuser@test.com",
        "password": "testpass1",
    })
    token = reg.json()["access_token"]

    # Delete account
    resp = await client.request(
        "DELETE", "/auth/account",
        headers={"Authorization": f"Bearer {token}"},
        json={"password": "testpass1"},
    )
    assert resp.status_code == 204

    # Token should no longer work (user deleted)
    me_resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_account_wrong_password(client: AsyncClient):
    reg = await client.post("/auth/register", json={
        "username": "nodelete2", "email": "nodelete2@test.com",
        "password": "correctpass",
    })
    token = reg.json()["access_token"]

    resp = await client.request(
        "DELETE", "/auth/account",
        headers={"Authorization": f"Bearer {token}"},
        json={"password": "wrongpass1"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_full_register_login_me_flow(client: AsyncClient):
    """Integration: register → login → me → verify consistency."""
    # Register
    reg = await client.post("/auth/register", json={
        "username": "fullflowuser", "email": "fullflowuser@test.com",
        "password": "flowpass1",
    })
    assert reg.status_code == 201
    reg_data = reg.json()

    # Login with same credentials
    login_resp = await client.post("/auth/login", json={
        "username": "fullflowuser",
        "password": "flowpass1",
    })
    assert login_resp.status_code == 200
    login_token = login_resp.json()["access_token"]

    # Me with login token
    me_resp = await client.get("/auth/me", headers={
        "Authorization": f"Bearer {login_token}"
    })
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["username"] == "fullflowuser"
    assert me_data["id"] == reg_data["id"]


@pytest.mark.asyncio
async def test_register_login_refresh_me_flow(client: AsyncClient):
    """Integration: register → login → refresh → me with refreshed token."""
    # Register
    await client.post("/auth/register", json={
        "username": "refreshflowuser", "email": "refreshflowuser@test.com",
        "password": "testpass1",
    })

    # Login
    login_resp = await client.post("/auth/login", json={
        "username": "refreshflowuser",
        "password": "testpass1",
    })
    refresh_token = login_resp.json()["refresh_token"]

    # Refresh
    refresh_resp = await client.post("/auth/refresh", json={
        "refresh_token": refresh_token,
    })
    new_access = refresh_resp.json()["access_token"]

    # Me with refreshed token
    me_resp = await client.get("/auth/me", headers={
        "Authorization": f"Bearer {new_access}"
    })
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "refreshflowuser"
