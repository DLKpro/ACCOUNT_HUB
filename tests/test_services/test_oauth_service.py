"""Unit tests for oauth_service — state management and initiation logic.

External HTTP calls (token exchange, userinfo) are not tested here since they
require real provider credentials. Integration tests mock those calls.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.db.models import OAuthState, User
from account_hub.oauth.providers import (
    FlowType,
    OAuthProviderConfig,
    _registry,
    register_provider,
)
from account_hub.security.hashing import hash_password
from account_hub.services.oauth_service import (
    InvalidStateError,
    handle_oauth_callback,
    initiate_oauth,
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
