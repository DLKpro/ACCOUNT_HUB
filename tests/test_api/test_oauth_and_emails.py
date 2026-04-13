"""Integration tests for OAuth and email endpoints.

These tests exercise the full stack: HTTP → routers → services → security → DB.
OAuth token exchange with real providers is NOT tested (requires credentials).
We test initiation, state management, email CRUD, and cross-module communication.
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from account_hub.oauth.providers import (
    FlowType,
    OAuthProviderConfig,
    _registry,
    register_provider,
)
from account_hub.services.oauth_service import (
    DeviceCodePendingError,
    EmailAlreadyLinkedError,
    InitiateResult,
    LinkResult,
    TokenExchangeFailedError,
    UserInfoFailedError,
)
from tests.helpers import auth_headers, register_user


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


# --- OAuth Initiate ---


@pytest.mark.asyncio
async def test_initiate_returns_auth_url(client: AsyncClient):
    token = await register_user(client)
    resp = await client.post(
        "/oauth/initiate",
        headers=auth_headers(token),
        json={"provider": "testprov", "redirect_port": 49000},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["auth_url"] is not None
    assert "example.com/auth" in data["auth_url"]
    assert data["state"] is not None


@pytest.mark.asyncio
async def test_initiate_unknown_provider(client: AsyncClient):
    token = await register_user(client)
    resp = await client.post(
        "/oauth/initiate",
        headers=auth_headers(token),
        json={"provider": "nonexistent", "redirect_port": 49000},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_initiate_requiresauth_headers(client: AsyncClient):
    resp = await client.post(
        "/oauth/initiate",
        json={"provider": "testprov", "redirect_port": 49000},
    )
    assert resp.status_code in (401, 403)


# --- OAuth Callback ---


@pytest.mark.asyncio
async def test_callback_invalid_state(client: AsyncClient):
    token = await register_user(client)
    resp = await client.post(
        "/oauth/callback",
        headers=auth_headers(token),
        json={"provider": "testprov", "code": "fake", "state": "bad-state"},
    )
    assert resp.status_code == 400


# --- Email List (empty initially) ---


@pytest.mark.asyncio
async def test_list_emails_shows_primary(client: AsyncClient):
    token = await register_user(client)
    resp = await client.get("/emails", headers=auth_headers(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["is_primary"] is True


@pytest.mark.asyncio
async def test_list_emails_requiresauth_headers(client: AsyncClient):
    resp = await client.get("/emails")
    assert resp.status_code in (401, 403)


# --- Email Delete ---


@pytest.mark.asyncio
async def test_delete_nonexistent_email(client: AsyncClient):
    token = await register_user(client)
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/emails/{fake_id}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_invalid_email_id(client: AsyncClient):
    token = await register_user(client)
    resp = await client.delete("/emails/not-a-uuid", headers=auth_headers(token))
    assert resp.status_code == 400


# --- Cross-module integration: auth + emails ---


@pytest.mark.asyncio
async def test_deleted_user_cannot_list_emails(client: AsyncClient):
    """After deleting an account, the token should no longer work for email endpoints."""
    resp = await client.post("/auth/register", json={
        "username": "deletedemails", "email": "deletedemails@test.com", "password": "testpass1"
    })
    token = resp.json()["access_token"]

    # Delete account
    await client.request("DELETE", "/auth/account",
        headers=auth_headers(token), json={"password": "testpass1"})

    # Try to list emails with the now-invalid token
    resp = await client.get("/emails", headers=auth_headers(token))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_initiate_state_scoped_to_user(client: AsyncClient):
    """State created by one user should not work for another."""
    token1 = await register_user(client, "stateuser1")
    token2 = await register_user(client, "stateuser2")

    # User 1 initiates
    resp = await client.post(
        "/oauth/initiate",
        headers=auth_headers(token1),
        json={"provider": "testprov", "redirect_port": 49000},
    )
    state = resp.json()["state"]

    # User 2 tries to use user 1's state
    resp = await client.post(
        "/oauth/callback",
        headers=auth_headers(token2),
        json={"provider": "testprov", "code": "fake", "state": state},
    )
    assert resp.status_code == 400  # Invalid state for this user


@pytest.mark.asyncio
async def test_full_auth_then_initiate_flow(client: AsyncClient):
    """Integration: register → login → initiate OAuth → verify state exists."""
    # Register
    reg = await client.post("/auth/register", json={
        "username": "fullflowemailuser",
        "email": "fullflowemailuser@test.com",
        "password": "testpass1",
    })
    assert reg.status_code == 201

    # Login
    login = await client.post("/auth/login", json={
        "username": "fullflowemailuser", "password": "testpass1"
    })
    token = login.json()["access_token"]

    # Initiate OAuth
    init = await client.post(
        "/oauth/initiate",
        headers=auth_headers(token),
        json={"provider": "testprov", "redirect_port": 49001},
    )
    assert init.status_code == 200
    assert init.json()["auth_url"] is not None

    # Verify email list only has the primary email (no OAuth callback completed)
    emails = await client.get("/emails", headers=auth_headers(token))
    assert emails.status_code == 200
    assert len(emails.json()) == 1  # just the primary account email
    assert emails.json()[0]["is_primary"] is True


# --- Device Code Initiate (mocked service) ---


@pytest.mark.asyncio
async def test_initiate_device_code_returns_user_code(client: AsyncClient):
    """Initiating with a device code provider returns user_code and verification_uri."""
    token = await register_user(client)

    mock_result = InitiateResult(
        state="state-xyz",
        user_code="ABCD-1234",
        verification_uri="https://example.com/activate",
        device_code="dev-code-abc",
        interval=5,
    )
    with patch(
        "account_hub.api.routers.oauth.initiate_oauth",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        resp = await client.post(
            "/oauth/initiate",
            headers=auth_headers(token),
            json={"provider": "testprov"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["user_code"] == "ABCD-1234"
    assert data["verification_uri"] == "https://example.com/activate"
    assert data["device_code"] == "dev-code-abc"
    assert data["interval"] == 5
    assert data["auth_url"] is None


@pytest.mark.asyncio
async def test_initiate_service_error_returns_502(client: AsyncClient):
    """When initiate_oauth raises OAuthServiceError, endpoint returns 502."""
    from account_hub.services.oauth_service import OAuthServiceError
    token = await register_user(client)

    with patch(
        "account_hub.api.routers.oauth.initiate_oauth",
        new_callable=AsyncMock,
        side_effect=OAuthServiceError("device code request failed"),
    ):
        resp = await client.post(
            "/oauth/initiate",
            headers=auth_headers(token),
            json={"provider": "testprov"},
        )

    assert resp.status_code == 502


# --- OAuth Poll endpoint ---


@pytest.mark.asyncio
async def test_poll_endpoint_pending(client: AsyncClient):
    """Poll returns 200 with status=pending when device code is still waiting."""
    token = await register_user(client)

    with patch(
        "account_hub.api.routers.oauth.poll_device_code",
        new_callable=AsyncMock,
        side_effect=DeviceCodePendingError("User has not yet authorized"),
    ):
        resp = await client.post(
            "/oauth/poll",
            headers=auth_headers(token),
            json={"provider": "testprov", "device_code": "dc_test"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_poll_endpoint_success(client: AsyncClient):
    """Poll returns 200 with linked email fields on success."""
    token = await register_user(client)

    link_result = LinkResult(
        linked_email_id=uuid.uuid4(),
        email_address="polled@example.com",
        provider="testprov",
    )

    with patch(
        "account_hub.api.routers.oauth.poll_device_code",
        new_callable=AsyncMock,
        return_value=link_result,
    ):
        resp = await client.post(
            "/oauth/poll",
            headers=auth_headers(token),
            json={"provider": "testprov", "device_code": "dc_test"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["email_address"] == "polled@example.com"
    assert data["provider"] == "testprov"
    assert data["linked_email_id"] == str(link_result.linked_email_id)


@pytest.mark.asyncio
async def test_poll_endpoint_already_linked(client: AsyncClient):
    """Poll returns 409 when the email is already linked."""
    token = await register_user(client)

    with patch(
        "account_hub.api.routers.oauth.poll_device_code",
        new_callable=AsyncMock,
        side_effect=EmailAlreadyLinkedError("already linked"),
    ):
        resp = await client.post(
            "/oauth/poll",
            headers=auth_headers(token),
            json={"provider": "testprov", "device_code": "dc_test"},
        )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_poll_endpoint_token_failure(client: AsyncClient):
    """Poll returns 502 when the token exchange fails."""
    token = await register_user(client)

    with patch(
        "account_hub.api.routers.oauth.poll_device_code",
        new_callable=AsyncMock,
        side_effect=TokenExchangeFailedError("poll failed"),
    ):
        resp = await client.post(
            "/oauth/poll",
            headers=auth_headers(token),
            json={"provider": "testprov", "device_code": "dc_test"},
        )

    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_poll_endpoint_requiresauth_headers(client: AsyncClient):
    """Poll without auth header returns 401 or 403."""
    resp = await client.post(
        "/oauth/poll",
        json={"provider": "testprov", "device_code": "dc_test"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_poll_endpoint_userinfo_failure(client: AsyncClient):
    """Poll returns 502 when userinfo retrieval fails."""
    token = await register_user(client)

    with patch(
        "account_hub.api.routers.oauth.poll_device_code",
        new_callable=AsyncMock,
        side_effect=UserInfoFailedError("Failed to retrieve user information"),
    ):
        resp = await client.post(
            "/oauth/poll",
            headers=auth_headers(token),
            json={"provider": "testprov", "device_code": "dc_test"},
        )

    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_callback_token_exchange_failure(client: AsyncClient):
    """Callback returns 502 when token exchange fails."""
    token = await register_user(client)

    with patch(
        "account_hub.api.routers.oauth.handle_oauth_callback",
        new_callable=AsyncMock,
        side_effect=TokenExchangeFailedError("token exchange failed"),
    ):
        resp = await client.post(
            "/oauth/callback",
            headers=auth_headers(token),
            json={"provider": "testprov", "code": "authcode", "state": "somestate"},
        )

    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_callback_email_already_linked(client: AsyncClient):
    """Callback returns 409 when email is already linked."""
    token = await register_user(client)

    with patch(
        "account_hub.api.routers.oauth.handle_oauth_callback",
        new_callable=AsyncMock,
        side_effect=EmailAlreadyLinkedError("already@example.com is already linked"),
    ):
        resp = await client.post(
            "/oauth/callback",
            headers=auth_headers(token),
            json={"provider": "testprov", "code": "authcode", "state": "somestate"},
        )

    assert resp.status_code == 409
