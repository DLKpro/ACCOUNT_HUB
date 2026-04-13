"""Unit tests for user_service — operates against the test database."""
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.db.models import User
from account_hub.security.hashing import verify_password
from account_hub.security.jwt import decode_token
from account_hub.services.user_service import (
    InvalidCredentials,
    InvalidToken,
    UsernameInvalid,
    UsernameTaken,
    authenticate_user,
    delete_account,
    refresh_tokens,
    register_user,
)


@pytest.mark.asyncio
async def test_register_user_creates_user(db_session: AsyncSession):
    user, tokens = await register_user(db_session, "testuser", "securepass123")
    assert user.username == "testuser"
    assert user.id is not None
    assert user.is_active is True


@pytest.mark.asyncio
async def test_register_user_hashes_password(db_session: AsyncSession):
    user, _ = await register_user(db_session, "hashcheck", "mypassword")
    assert user.password_hash != "mypassword"
    assert verify_password("mypassword", user.password_hash)


@pytest.mark.asyncio
async def test_register_user_returns_valid_tokens(db_session: AsyncSession):
    user, tokens = await register_user(db_session, "tokenuser", "pass123")
    access_uid = decode_token(tokens.access_token, "access")
    refresh_uid = decode_token(tokens.refresh_token, "refresh")
    assert access_uid == user.id
    assert refresh_uid == user.id


@pytest.mark.asyncio
async def test_register_user_lowercases_username(db_session: AsyncSession):
    user, _ = await register_user(db_session, "UpperCase", "pass")
    assert user.username == "uppercase"


@pytest.mark.asyncio
async def test_register_invalid_username_raises(db_session: AsyncSession):
    with pytest.raises(UsernameInvalid):
        await register_user(db_session, "ab", "pass")  # too short

    with pytest.raises(UsernameInvalid):
        await register_user(db_session, "has spaces", "pass")

    with pytest.raises(UsernameInvalid):
        await register_user(db_session, "CAPS!", "pass")


@pytest.mark.asyncio
async def test_register_duplicate_username_raises(db_session: AsyncSession):
    await register_user(db_session, "unique_user", "pass1")
    with pytest.raises(UsernameTaken):
        await register_user(db_session, "unique_user", "pass2")


@pytest.mark.asyncio
async def test_authenticate_user_succeeds(db_session: AsyncSession):
    await register_user(db_session, "logintest", "correct_password")
    user, tokens = await authenticate_user(db_session, "logintest", "correct_password")
    assert user.username == "logintest"
    assert tokens.access_token is not None


@pytest.mark.asyncio
async def test_authenticate_wrong_password_raises(db_session: AsyncSession):
    await register_user(db_session, "wrongpass", "right")
    with pytest.raises(InvalidCredentials):
        await authenticate_user(db_session, "wrongpass", "wrong")


@pytest.mark.asyncio
async def test_authenticate_nonexistent_user_raises(db_session: AsyncSession):
    with pytest.raises(InvalidCredentials):
        await authenticate_user(db_session, "ghost_user", "anything")


@pytest.mark.asyncio
async def test_refresh_tokens_returns_valid_pair(db_session: AsyncSession):
    user, tokens = await register_user(db_session, "refreshtest", "pass")
    new_tokens = await refresh_tokens(db_session, tokens.refresh_token)
    # New tokens should decode to the same user
    assert decode_token(new_tokens.access_token, "access") == user.id
    assert decode_token(new_tokens.refresh_token, "refresh") == user.id


@pytest.mark.asyncio
async def test_refresh_with_access_token_raises(db_session: AsyncSession):
    _, tokens = await register_user(db_session, "badrefresh", "pass")
    with pytest.raises(InvalidToken):
        await refresh_tokens(db_session, tokens.access_token)  # wrong token type


@pytest.mark.asyncio
async def test_refresh_with_garbage_raises(db_session: AsyncSession):
    with pytest.raises(InvalidToken):
        await refresh_tokens(db_session, "not-a-token")


@pytest.mark.asyncio
async def test_delete_account_removes_user(db_session: AsyncSession):
    user, _ = await register_user(db_session, "deleteme", "pass")
    await delete_account(db_session, user, "pass")
    result = await db_session.execute(select(User).where(User.id == user.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_account_wrong_password_raises(db_session: AsyncSession):
    user, _ = await register_user(db_session, "nodelete", "correct")
    with pytest.raises(InvalidCredentials):
        await delete_account(db_session, user, "wrong")
