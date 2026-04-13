"""Unit tests for oauth_service — state management and initiation logic.

External HTTP calls (token exchange, userinfo) are not tested here since they
require real provider credentials. Integration tests mock those calls.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.db.models import LinkedEmail, OAuthState, User
from account_hub.oauth.providers import (
    FlowType,
    OAuthProviderConfig,
    _registry,
    register_provider,
)
from account_hub.security.hashing import hash_password
from account_hub.services.oauth_service import (
    DeviceCodePendingError,
    EmailAlreadyLinkedError,
    InvalidStateError,
    TokenExchangeFailedError,
    UserInfoFailedError,
    _exchange_code,
    _get_user_info,
    _start_device_code_flow,
    handle_oauth_callback,
    initiate_oauth,
    poll_device_code,
)


@pytest.fixture(autouse=True)
def setup_test_provider():
    """Register a fake loopback provider for testing."""
    saved = dict(_registry)
    _registry.clear()
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
    _registry.clear()
    _registry.update(saved)


async def _create_test_user(db: AsyncSession) -> User:
    user = User(username="oauthuser", password_hash=hash_password("pass"))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_initiate_creates_state(db_session: AsyncSession):
    user = await _create_test_user(db_session)
    result = await initiate_oauth(db_session, user.id, "testprov", redirect_port=49000)

    assert result.auth_url is not None
    assert "example.com/auth" in result.auth_url
    assert "client_id=test-client-id" in result.auth_url
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A49000%2Fcallback" in result.auth_url
    assert result.state is not None


@pytest.mark.asyncio
async def test_initiate_stores_state_in_db(db_session: AsyncSession):
    user = await _create_test_user(db_session)
    result = await initiate_oauth(db_session, user.id, "testprov", redirect_port=49000)

    states = (await db_session.execute(select(OAuthState))).scalars().all()
    assert len(states) == 1
    assert states[0].state == result.state
    assert states[0].user_id == user.id
    assert states[0].provider == "testprov"
    assert states[0].redirect_port == 49000


@pytest.mark.asyncio
async def test_initiate_includes_scopes_in_url(db_session: AsyncSession):
    user = await _create_test_user(db_session)
    result = await initiate_oauth(db_session, user.id, "testprov", redirect_port=49000)
    assert "scope=email+profile" in result.auth_url


@pytest.mark.asyncio
async def test_initiate_unknown_provider_raises(db_session: AsyncSession):
    user = await _create_test_user(db_session)
    with pytest.raises(ValueError, match="Unknown OAuth provider"):
        await initiate_oauth(db_session, user.id, "nonexistent", redirect_port=49000)


@pytest.mark.asyncio
async def test_callback_invalid_state_raises(db_session: AsyncSession):
    user = await _create_test_user(db_session)
    with pytest.raises(InvalidStateError):
        await handle_oauth_callback(
            db_session, user.id, "testprov", code="fake", state="bad-state"
        )


# ---------------------------------------------------------------------------
# Helpers for mocking httpx
# ---------------------------------------------------------------------------


def _mock_httpx_response(status_code, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text or ""
    resp.json.return_value = json_data or {}
    return resp


def _mock_async_client(post_response=None, get_response=None):
    mock_client = AsyncMock()
    if post_response:
        mock_client.post.return_value = post_response
    if get_response:
        mock_client.get.return_value = get_response
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx, mock_client


# ---------------------------------------------------------------------------
# Device code provider fixture (non-autouse)
# ---------------------------------------------------------------------------


@pytest.fixture()
def setup_device_code_provider():
    register_provider(OAuthProviderConfig(
        name="testdevice",
        authorize_url="",
        token_url="https://example.com/token",
        userinfo_url="https://example.com/userinfo",
        scopes=["email"],
        flow_type=FlowType.DEVICE_CODE,
        client_id="device-client-id",
        client_secret="",
        device_code_url="https://example.com/devicecode",
    ))


# ---------------------------------------------------------------------------
# _exchange_code tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("account_hub.services.oauth_service.httpx.AsyncClient")
async def test_exchange_code_success(mock_async_client_cls):
    mock_ctx, mock_client = _mock_async_client(
        post_response=_mock_httpx_response(200, {"access_token": "tok", "refresh_token": "rt"}),
    )
    mock_async_client_cls.return_value = mock_ctx

    provider = _registry["testprov"]
    result = await _exchange_code(provider, "code", 49000, "testprov")

    assert result["access_token"] == "tok"
    assert result["refresh_token"] == "rt"
    mock_client.post.assert_awaited_once()


@pytest.mark.asyncio
@patch("account_hub.services.oauth_service.httpx.AsyncClient")
async def test_exchange_code_failure(mock_async_client_cls):
    mock_ctx, _ = _mock_async_client(
        post_response=_mock_httpx_response(400, text="bad request"),
    )
    mock_async_client_cls.return_value = mock_ctx

    provider = _registry["testprov"]
    with pytest.raises(TokenExchangeFailedError):
        await _exchange_code(provider, "code", 49000, "testprov")


@pytest.mark.asyncio
@patch("account_hub.services.oauth_service.httpx.AsyncClient")
async def test_exchange_code_apple_redirect(mock_async_client_cls):
    """Apple provider must use dlopro.com/callback as redirect_uri."""
    register_provider(OAuthProviderConfig(
        name="apple",
        authorize_url="https://appleid.apple.com/auth/authorize",
        token_url="https://appleid.apple.com/auth/token",
        userinfo_url="",
        scopes=["email"],
        flow_type=FlowType.LOOPBACK,
        client_id="apple-client-id",
        client_secret="apple-client-secret",
    ))
    mock_ctx, mock_client = _mock_async_client(
        post_response=_mock_httpx_response(200, {"access_token": "apple-tok"}),
    )
    mock_async_client_cls.return_value = mock_ctx

    provider = _registry["apple"]
    await _exchange_code(provider, "code", 49000, "apple")

    call_kwargs = mock_client.post.call_args
    post_data = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
    assert post_data["redirect_uri"] == "https://dlopro.com/callback"


# ---------------------------------------------------------------------------
# _get_user_info tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("account_hub.services.oauth_service.httpx.AsyncClient")
async def test_get_user_info_success(mock_async_client_cls):
    mock_ctx, mock_client = _mock_async_client(
        get_response=_mock_httpx_response(200, {"email": "a@b.com", "sub": "123"}),
    )
    mock_async_client_cls.return_value = mock_ctx

    provider = _registry["testprov"]
    result = await _get_user_info(provider, "access-tok")

    assert result["email"] == "a@b.com"
    assert result["sub"] == "123"
    mock_client.get.assert_awaited_once()


@pytest.mark.asyncio
@patch("account_hub.services.oauth_service.httpx.AsyncClient")
async def test_get_user_info_failure(mock_async_client_cls):
    mock_ctx, _ = _mock_async_client(
        get_response=_mock_httpx_response(401, text="unauthorized"),
    )
    mock_async_client_cls.return_value = mock_ctx

    provider = _registry["testprov"]
    with pytest.raises(UserInfoFailedError):
        await _get_user_info(provider, "bad-tok")


@pytest.mark.asyncio
async def test_get_user_info_no_url():
    """When userinfo_url is empty, _get_user_info should return {}."""
    provider = OAuthProviderConfig(
        name="nouserinfo",
        authorize_url="",
        token_url="https://example.com/token",
        userinfo_url="",
        scopes=["email"],
        flow_type=FlowType.LOOPBACK,
        client_id="cid",
        client_secret="csec",
    )
    result = await _get_user_info(provider, "any-token")
    assert result == {}


# ---------------------------------------------------------------------------
# _start_device_code_flow tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("account_hub.services.oauth_service.httpx.AsyncClient")
async def test_start_device_code_success(mock_async_client_cls, setup_device_code_provider):
    device_resp = {
        "user_code": "ABCD-1234",
        "verification_uri": "https://example.com/activate",
        "device_code": "dev-code-xyz",
        "interval": 5,
    }
    mock_ctx, _ = _mock_async_client(
        post_response=_mock_httpx_response(200, device_resp),
    )
    mock_async_client_cls.return_value = mock_ctx

    provider = _registry["testdevice"]
    result = await _start_device_code_flow(provider, "state-abc")

    assert result.user_code == "ABCD-1234"
    assert result.verification_uri == "https://example.com/activate"
    assert result.device_code == "dev-code-xyz"
    assert result.interval == 5
    assert result.state == "state-abc"


@pytest.mark.asyncio
@patch("account_hub.services.oauth_service.httpx.AsyncClient")
async def test_start_device_code_failure(mock_async_client_cls, setup_device_code_provider):
    mock_ctx, _ = _mock_async_client(
        post_response=_mock_httpx_response(400, text="bad request"),
    )
    mock_async_client_cls.return_value = mock_ctx

    provider = _registry["testdevice"]
    with pytest.raises(TokenExchangeFailedError):
        await _start_device_code_flow(provider, "state-abc")


# ---------------------------------------------------------------------------
# poll_device_code tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("account_hub.services.oauth_service.httpx.AsyncClient")
async def test_poll_success(
    mock_async_client_cls, setup_device_code_provider, db_session: AsyncSession,
):
    user = await _create_test_user(db_session)

    token_resp = _mock_httpx_response(200, {
        "access_token": "poll-tok",
        "refresh_token": "poll-rt",
        "expires_in": 3600,
    })
    userinfo_resp = _mock_httpx_response(200, {
        "email": "poll@example.com",
        "id": "user-id-123",
    })
    # Both token exchange (post) and userinfo (get) go through the same mock client
    mock_ctx, mock_client = _mock_async_client(
        post_response=token_resp,
        get_response=userinfo_resp,
    )
    mock_async_client_cls.return_value = mock_ctx

    result = await poll_device_code(db_session, user.id, "testdevice", "dev-code-xyz")

    assert result.email_address == "poll@example.com"
    assert result.provider == "testdevice"

    # Verify the email was stored in the DB
    rows = (await db_session.execute(
        select(LinkedEmail).where(LinkedEmail.user_id == user.id)
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].email_address == "poll@example.com"


@pytest.mark.asyncio
@patch("account_hub.services.oauth_service.httpx.AsyncClient")
async def test_poll_pending(
    mock_async_client_cls, setup_device_code_provider, db_session: AsyncSession,
):
    user = await _create_test_user(db_session)

    mock_ctx, _ = _mock_async_client(
        post_response=_mock_httpx_response(428, {"error": "authorization_pending"}),
    )
    mock_async_client_cls.return_value = mock_ctx

    with pytest.raises(DeviceCodePendingError):
        await poll_device_code(db_session, user.id, "testdevice", "dev-code-xyz")


@pytest.mark.asyncio
@patch("account_hub.services.oauth_service.httpx.AsyncClient")
async def test_poll_slow_down(
    mock_async_client_cls, setup_device_code_provider, db_session: AsyncSession,
):
    user = await _create_test_user(db_session)

    mock_ctx, _ = _mock_async_client(
        post_response=_mock_httpx_response(428, {"error": "slow_down"}),
    )
    mock_async_client_cls.return_value = mock_ctx

    with pytest.raises(DeviceCodePendingError):
        await poll_device_code(db_session, user.id, "testdevice", "dev-code-xyz")


@pytest.mark.asyncio
@patch("account_hub.services.oauth_service.httpx.AsyncClient")
async def test_poll_token_failure(
    mock_async_client_cls, setup_device_code_provider, db_session: AsyncSession,
):
    user = await _create_test_user(db_session)

    mock_ctx, _ = _mock_async_client(
        post_response=_mock_httpx_response(400, {"error": "something_else"}),
    )
    mock_async_client_cls.return_value = mock_ctx

    with pytest.raises(TokenExchangeFailedError):
        await poll_device_code(db_session, user.id, "testdevice", "dev-code-xyz")


@pytest.mark.asyncio
@patch("account_hub.services.oauth_service.httpx.AsyncClient")
async def test_poll_already_linked(
    mock_async_client_cls, setup_device_code_provider, db_session: AsyncSession,
):
    user = await _create_test_user(db_session)

    # Pre-insert a linked email so the poll will hit the duplicate check
    from account_hub.security.encryption import encrypt_token
    existing = LinkedEmail(
        user_id=user.id,
        email_address="already@example.com",
        provider="testdevice",
        access_token_enc=encrypt_token("old-tok"),
        is_verified=True,
    )
    db_session.add(existing)
    await db_session.commit()

    token_resp = _mock_httpx_response(200, {
        "access_token": "new-tok",
        "refresh_token": "new-rt",
    })
    userinfo_resp = _mock_httpx_response(200, {
        "email": "already@example.com",
        "id": "user-id-456",
    })
    mock_ctx, _ = _mock_async_client(
        post_response=token_resp,
        get_response=userinfo_resp,
    )
    mock_async_client_cls.return_value = mock_ctx

    with pytest.raises(EmailAlreadyLinkedError):
        await poll_device_code(db_session, user.id, "testdevice", "dev-code-xyz")
