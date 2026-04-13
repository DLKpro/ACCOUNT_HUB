"""Unit tests for email_service — linked email CRUD against the test DB."""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.services.email_service import (
    EmailNotFoundError,
    get_linked_email,
    list_linked_emails,
    unlink_email,
)
from tests.helpers import create_linked_email, create_test_user


@pytest.mark.asyncio
async def test_list_linked_emails_empty(db_session: AsyncSession):
    user = await create_test_user(db_session)
    result = await list_linked_emails(db_session, user.id)
    assert result == []


@pytest.mark.asyncio
async def test_list_linked_emails_returns_all(db_session: AsyncSession):
    user = await create_test_user(db_session)
    await create_linked_email(db_session, user, "a@gmail.com", "google")
    await create_linked_email(db_session, user, "b@outlook.com", "microsoft")

    result = await list_linked_emails(db_session, user.id)
    assert len(result) == 2
    emails = {e.email_address for e in result}
    assert emails == {"a@gmail.com", "b@outlook.com"}


@pytest.mark.asyncio
async def test_list_emails_only_returns_own(db_session: AsyncSession):
    user1 = await create_test_user(db_session, "user1")
    user2 = await create_test_user(db_session, "user2")
    await create_linked_email(db_session, user1, "user1@gmail.com")
    await create_linked_email(db_session, user2, "user2@gmail.com")

    result = await list_linked_emails(db_session, user1.id)
    assert len(result) == 1
    assert result[0].email_address == "user1@gmail.com"


@pytest.mark.asyncio
async def test_get_linked_email(db_session: AsyncSession):
    user = await create_test_user(db_session)
    linked = await create_linked_email(db_session, user)

    result = await get_linked_email(db_session, user.id, linked.id)
    assert result.email_address == "test@gmail.com"


@pytest.mark.asyncio
async def test_get_linked_email_not_found(db_session: AsyncSession):
    user = await create_test_user(db_session)
    with pytest.raises(EmailNotFoundError):
        await get_linked_email(db_session, user.id, uuid.uuid4())


@pytest.mark.asyncio
async def test_get_linked_email_wrong_user(db_session: AsyncSession):
    user1 = await create_test_user(db_session, "owner")
    user2 = await create_test_user(db_session, "other")
    linked = await create_linked_email(db_session, user1)

    with pytest.raises(EmailNotFoundError):
        await get_linked_email(db_session, user2.id, linked.id)


@pytest.mark.asyncio
async def test_unlink_email(db_session: AsyncSession):
    user = await create_test_user(db_session)
    linked = await create_linked_email(db_session, user)

    await unlink_email(db_session, user.id, linked.id)

    result = await list_linked_emails(db_session, user.id)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_unlink_email_not_found(db_session: AsyncSession):
    user = await create_test_user(db_session)
    with pytest.raises(EmailNotFoundError):
        await unlink_email(db_session, user.id, uuid.uuid4())
