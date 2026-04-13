"""Unit tests for user_service — operates against the test database."""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.db.models import User
from account_hub.security.hashing import verify_password
from account_hub.security.jwt import decode_token
from account_hub.services.user_service import (
    InvalidCredentialsError,
    InvalidTokenError,
    UsernameInvalidError,
    UsernameTakenError,
    authenticate_user,
    delete_account,
    refresh_tokens,
    register_user,
)


@pytest.mark.asyncio
async def test_register_user_creates_user(db_session: AsyncSession):
    user, tokens = await register_user(db_session, "testuser", "testuser@test.com", "securepass123")
    assert user.username == "testuser"
    assert user.id is not None
    assert user.is_active is True


@pytest.mark.asyncio
async def test_register_user_hashes_password(db_session: AsyncSession):
    user, _ = await register_user(db_session, "hashcheck", "hashcheck@test.com", "mypassword")
    assert user.password_hash != "mypassword"
    assert verify_password("mypassword", user.password_hash)


@pytest.mark.asyncio
async def test_register_user_returns_valid_tokens(db_session: AsyncSession):
    user, tokens = await register_user(db_session, "tokenuser", "tokenuser@test.com", "testpass123")
    access_uid = decode_token(tokens.access_token, "access")
    refresh_uid = decode_token(tokens.refresh_token, "refresh")
    assert access_uid == user.id
    assert refresh_uid == user.id


@pytest.mark.asyncio
async def test_register_user_lowercases_username(db_session: AsyncSession):
    user, _ = await register_user(db_session, "UpperCase", "UpperCase@test.com", "testpass1")
    assert user.username == "uppercase"


@pytest.mark.asyncio
async def test_register_invalid_username_raises(db_session: AsyncSession):
    with pytest.raises(UsernameInvalidError):
        await register_user(db_session, "ab", "ab@test.com", "testpass1")  # too short

    with pytest.raises(UsernameInvalidError):
        await register_user(db_session, "has spaces", "has spaces@test.com", "testpass1")

    with pytest.raises(UsernameInvalidError):
        await register_user(db_session, "CAPS!", "CAPS!@test.com", "testpass1")


@pytest.mark.asyncio
async def test_register_duplicate_username_raises(db_session: AsyncSession):
    await register_user(db_session, "unique_user", "unique_user@test.com", "testpass1")
    with pytest.raises(UsernameTakenError):
        await register_user(db_session, "unique_user", "unique_user2@test.com", "testpass2")


@pytest.mark.asyncio
async def test_authenticate_user_succeeds(db_session: AsyncSession):
    await register_user(db_session, "logintest", "logintest@test.com", "correct_password")
    user, tokens = await authenticate_user(db_session, "logintest", "correct_password")
    assert user.username == "logintest"
    assert tokens.access_token is not None


@pytest.mark.asyncio
async def test_authenticate_wrong_password_raises(db_session: AsyncSession):
    await register_user(db_session, "wrongpass", "wrongpass@test.com", "rightpass1")
    with pytest.raises(InvalidCredentialsError):
        await authenticate_user(db_session, "wrongpass", "wrongpass1")


@pytest.mark.asyncio
async def test_authenticate_nonexistent_user_raises(db_session: AsyncSession):
    with pytest.raises(InvalidCredentialsError):
        await authenticate_user(db_session, "ghost_user", "anything")


@pytest.mark.asyncio
async def test_refresh_tokens_returns_valid_pair(db_session: AsyncSession):
    user, tokens = await register_user(db_session, "refreshtest", "refreshtest@test.com", "testpass1")
    new_tokens = await refresh_tokens(db_session, tokens.refresh_token)
    # New tokens should decode to the same user
    assert decode_token(new_tokens.access_token, "access") == user.id
    assert decode_token(new_tokens.refresh_token, "refresh") == user.id


@pytest.mark.asyncio
async def test_refresh_with_access_token_raises(db_session: AsyncSession):
    _, tokens = await register_user(db_session, "badrefresh", "badrefresh@test.com", "testpass1")
    with pytest.raises(InvalidTokenError):
        await refresh_tokens(db_session, tokens.access_token)  # wrong token type


@pytest.mark.asyncio
async def test_refresh_with_garbage_raises(db_session: AsyncSession):
    with pytest.raises(InvalidTokenError):
        await refresh_tokens(db_session, "not-a-token")


@pytest.mark.asyncio
async def test_delete_account_removes_user(db_session: AsyncSession):
    user, _ = await register_user(db_session, "deleteme", "deleteme@test.com", "testpass1")
    await delete_account(db_session, user, "testpass1")
    result = await db_session.execute(select(User).where(User.id == user.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_account_wrong_password_raises(db_session: AsyncSession):
    user, _ = await register_user(db_session, "nodelete", "nodelete@test.com", "correctpass")
    with pytest.raises(InvalidCredentialsError):
        await delete_account(db_session, user, "wrongpass1")
