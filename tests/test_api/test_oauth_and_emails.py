"""Integration tests for OAuth and email endpoints.

These tests exercise the full stack: HTTP → routers → services → security → DB.
OAuth token exchange with real providers is NOT tested (requires credentials).
We test initiation, state management, email CRUD, and cross-module communication.
"""
import uuid

import pytest
from httpx import AsyncClient

from account_hub.oauth.providers import (
    FlowType,
    OAuthProviderConfig,
    _registry,
    register_provider,
)


@pytest.fixture(autouse=True)
def setup_test_provider():
    """Ensure a test provider is registered for all tests in this module."""
    if "testprov" not in _registry:
        register_provider(OAuthProviderConfig(
            name="testprov",
            authorize_url="https://example.com/auth",
            token_url="https://example.com/token",
            userinfo_url="https://example.com/userinfo",
            scopes=["email", "profile"],
            flow_type=FlowType.LOOPBACK,
            client_id="test-client-id",
            client_secret="test-client-secret",
        ))
    yield


async def _register_and_get_token(client: AsyncClient, username: str = None) -> str:
    """Helper: register a user and return the access token."""
    uname = username or f"user_{uuid.uuid4().hex[:8]}"
    resp = await client.post("/auth/register", json={
        "username": uname, "password": "testpass"
    })
    assert resp.status_code == 201
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- OAuth Initiate ---


@pytest.mark.asyncio
async def test_initiate_returns_auth_url(client: AsyncClient):
    token = await _register_and_get_token(client)
    resp = await client.post(
        "/oauth/initiate",
        headers=_auth(token),
        json={"provider": "testprov", "redirect_port": 49000},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["auth_url"] is not None
    assert "example.com/auth" in data["auth_url"]
    assert data["state"] is not None


@pytest.mark.asyncio
async def test_initiate_unknown_provider(client: AsyncClient):
    token = await _register_and_get_token(client)
    resp = await client.post(
        "/oauth/initiate",
        headers=_auth(token),
        json={"provider": "nonexistent", "redirect_port": 49000},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_initiate_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/oauth/initiate",
        json={"provider": "testprov", "redirect_port": 49000},
    )
    assert resp.status_code in (401, 403)


# --- OAuth Callback ---


@pytest.mark.asyncio
async def test_callback_invalid_state(client: AsyncClient):
    token = await _register_and_get_token(client)
    resp = await client.post(
        "/oauth/callback",
        headers=_auth(token),
        json={"provider": "testprov", "code": "fake", "state": "bad-state"},
    )
    assert resp.status_code == 400


# --- Email List (empty initially) ---


@pytest.mark.asyncio
async def test_list_emails_empty(client: AsyncClient):
    token = await _register_and_get_token(client)
    resp = await client.get("/emails", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_emails_requires_auth(client: AsyncClient):
    resp = await client.get("/emails")
    assert resp.status_code in (401, 403)


# --- Email Delete ---


@pytest.mark.asyncio
async def test_delete_nonexistent_email(client: AsyncClient):
    token = await _register_and_get_token(client)
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/emails/{fake_id}", headers=_auth(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_invalid_email_id(client: AsyncClient):
    token = await _register_and_get_token(client)
    resp = await client.delete("/emails/not-a-uuid", headers=_auth(token))
    assert resp.status_code == 400


# --- Cross-module integration: auth + emails ---


@pytest.mark.asyncio
async def test_deleted_user_cannot_list_emails(client: AsyncClient):
    """After deleting an account, the token should no longer work for email endpoints."""
    resp = await client.post("/auth/register", json={
        "username": "deletedemails", "password": "pass"
    })
    token = resp.json()["access_token"]

    # Delete account
    await client.request("DELETE", "/auth/account",
        headers=_auth(token), json={"password": "pass"})

    # Try to list emails with the now-invalid token
    resp = await client.get("/emails", headers=_auth(token))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_initiate_state_scoped_to_user(client: AsyncClient):
    """State created by one user should not work for another."""
    token1 = await _register_and_get_token(client, "stateuser1")
    token2 = await _register_and_get_token(client, "stateuser2")

    # User 1 initiates
    resp = await client.post(
        "/oauth/initiate",
        headers=_auth(token1),
        json={"provider": "testprov", "redirect_port": 49000},
    )
    state = resp.json()["state"]

    # User 2 tries to use user 1's state
    resp = await client.post(
        "/oauth/callback",
        headers=_auth(token2),
        json={"provider": "testprov", "code": "fake", "state": state},
    )
    assert resp.status_code == 400  # Invalid state for this user


@pytest.mark.asyncio
async def test_full_auth_then_initiate_flow(client: AsyncClient):
    """Integration: register → login → initiate OAuth → verify state exists."""
    # Register
    reg = await client.post("/auth/register", json={
        "username": "fullflowemailuser", "password": "pass"
    })
    assert reg.status_code == 201

    # Login
    login = await client.post("/auth/login", json={
        "username": "fullflowemailuser", "password": "pass"
    })
    token = login.json()["access_token"]

    # Initiate OAuth
    init = await client.post(
        "/oauth/initiate",
        headers=_auth(token),
        json={"provider": "testprov", "redirect_port": 49001},
    )
    assert init.status_code == 200
    assert init.json()["auth_url"] is not None

    # Verify email list is still empty (no callback completed)
    emails = await client.get("/emails", headers=_auth(token))
    assert emails.status_code == 200
    assert emails.json() == []
