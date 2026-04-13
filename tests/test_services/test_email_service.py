"""Unit tests for email_service — linked email CRUD against the test DB."""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.db.models import LinkedEmail, User
from account_hub.security.encryption import encrypt_token
from account_hub.security.hashing import hash_password
from account_hub.services.email_service import (
    EmailNotFound,
    get_linked_email,
    list_linked_emails,
    unlink_email,
)


async def _create_user(db: AsyncSession, username: str = "emailuser") -> User:
    user = User(username=username, password_hash=hash_password("pass"))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _link_email(
    db: AsyncSession, user: User, email: str = "test@gmail.com", provider: str = "google"
) -> LinkedEmail:
    linked = LinkedEmail(
        user_id=user.id,
        email_address=email,
        provider=provider,
        access_token_enc=encrypt_token("fake-access-token"),
        is_verified=True,
    )
    db.add(linked)
    await db.commit()
    await db.refresh(linked)
    return linked


@pytest.mark.asyncio
async def test_list_linked_emails_empty(db_session: AsyncSession):
    user = await _create_user(db_session)
    result = await list_linked_emails(db_session, user.id)
    assert result == []


@pytest.mark.asyncio
async def test_list_linked_emails_returns_all(db_session: AsyncSession):
    user = await _create_user(db_session)
    await _link_email(db_session, user, "a@gmail.com", "google")
    await _link_email(db_session, user, "b@outlook.com", "microsoft")

    result = await list_linked_emails(db_session, user.id)
    assert len(result) == 2
    emails = {e.email_address for e in result}
    assert emails == {"a@gmail.com", "b@outlook.com"}


@pytest.mark.asyncio
async def test_list_emails_only_returns_own(db_session: AsyncSession):
    user1 = await _create_user(db_session, "user1")
    user2 = await _create_user(db_session, "user2")
    await _link_email(db_session, user1, "user1@gmail.com")
    await _link_email(db_session, user2, "user2@gmail.com")

    result = await list_linked_emails(db_session, user1.id)
    assert len(result) == 1
    assert result[0].email_address == "user1@gmail.com"


@pytest.mark.asyncio
async def test_get_linked_email(db_session: AsyncSession):
    user = await _create_user(db_session)
    linked = await _link_email(db_session, user)

    result = await get_linked_email(db_session, user.id, linked.id)
    assert result.email_address == "test@gmail.com"


@pytest.mark.asyncio
async def test_get_linked_email_not_found(db_session: AsyncSession):
    user = await _create_user(db_session)
    with pytest.raises(EmailNotFound):
        await get_linked_email(db_session, user.id, uuid.uuid4())


@pytest.mark.asyncio
async def test_get_linked_email_wrong_user(db_session: AsyncSession):
    user1 = await _create_user(db_session, "owner")
    user2 = await _create_user(db_session, "other")
    linked = await _link_email(db_session, user1)

    with pytest.raises(EmailNotFound):
        await get_linked_email(db_session, user2.id, linked.id)


@pytest.mark.asyncio
async def test_unlink_email(db_session: AsyncSession):
    user = await _create_user(db_session)
    linked = await _link_email(db_session, user)

    await unlink_email(db_session, user.id, linked.id)

    result = await list_linked_emails(db_session, user.id)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_unlink_email_not_found(db_session: AsyncSession):
    user = await _create_user(db_session)
    with pytest.raises(EmailNotFound):
        await unlink_email(db_session, user.id, uuid.uuid4())
