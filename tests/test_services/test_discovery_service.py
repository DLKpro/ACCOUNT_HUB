"""Unit tests for discovery_service — scan orchestration against test DB."""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.services.discovery_service import (
    ScanNotFoundError,
    get_scan_history,
    get_scan_results,
    get_scan_session,
    start_scan,
)
from tests.helpers import create_linked_email, create_test_user


@pytest.mark.asyncio
async def test_start_scan_no_emails(db_session: AsyncSession):
    user = await create_test_user(db_session)
    session = await start_scan(db_session, user.id)
    assert session.status == "completed"
    assert session.emails_scanned == 0
    assert session.accounts_found == 0


@pytest.mark.asyncio
async def test_start_scan_with_linked_email(db_session: AsyncSession):
    user = await create_test_user(db_session)
    await create_linked_email(db_session, user, "test@gmail.com", "google")

    session = await start_scan(db_session, user.id)
    assert session.status == "completed"
    assert session.emails_scanned == 1
    # OAuthProfileScanner should find at least the provider account
    assert session.accounts_found >= 1


@pytest.mark.asyncio
async def test_start_scan_with_multiple_emails(db_session: AsyncSession):
    user = await create_test_user(db_session)
    await create_linked_email(db_session, user, "a@gmail.com", "google")
    await create_linked_email(db_session, user, "b@outlook.com", "microsoft")

    session = await start_scan(db_session, user.id)
    assert session.status == "completed"
    assert session.emails_scanned == 2
    assert session.accounts_found >= 2


@pytest.mark.asyncio
async def test_scan_results_contain_oauth_profile(db_session: AsyncSession):
    user = await create_test_user(db_session)
    await create_linked_email(db_session, user, "user@gmail.com", "google")

    session = await start_scan(db_session, user.id)
    results = await get_scan_results(db_session, session.id)

    google_results = [r for r in results if r.source == "oauth_profile"]
    assert len(google_results) == 1
    assert google_results[0].service_name == "Google Account"
    assert google_results[0].email_address == "user@gmail.com"
    assert google_results[0].confidence == "confirmed"


@pytest.mark.asyncio
async def test_get_scan_session(db_session: AsyncSession):
    user = await create_test_user(db_session)
    session = await start_scan(db_session, user.id)

    fetched = await get_scan_session(db_session, user.id, session.id)
    assert fetched.id == session.id
    assert fetched.status == "completed"


@pytest.mark.asyncio
async def test_get_scan_session_not_found(db_session: AsyncSession):
    user = await create_test_user(db_session)
    with pytest.raises(ScanNotFoundError):
        await get_scan_session(db_session, user.id, uuid.uuid4())


@pytest.mark.asyncio
async def test_get_scan_session_wrong_user(db_session: AsyncSession):
    user1 = await create_test_user(db_session, "scanowner")
    user2 = await create_test_user(db_session, "scanother")
    session = await start_scan(db_session, user1.id)

    with pytest.raises(ScanNotFoundError):
        await get_scan_session(db_session, user2.id, session.id)


@pytest.mark.asyncio
async def test_scan_history(db_session: AsyncSession):
    user = await create_test_user(db_session)
    await start_scan(db_session, user.id)
    await start_scan(db_session, user.id)

    history = await get_scan_history(db_session, user.id)
    assert len(history) == 2


@pytest.mark.asyncio
async def test_scan_history_limit(db_session: AsyncSession):
    user = await create_test_user(db_session)
    for _ in range(5):
        await start_scan(db_session, user.id)

    history = await get_scan_history(db_session, user.id, limit=3)
    assert len(history) == 3


@pytest.mark.asyncio
async def test_scan_deduplicates_results(db_session: AsyncSession):
    """Running multiple scans should not produce duplicates within a single scan."""
    user = await create_test_user(db_session)
    await create_linked_email(db_session, user, "user@gmail.com", "google")

    session = await start_scan(db_session, user.id)
    results = await get_scan_results(db_session, session.id)

    # Should have exactly 1 oauth_profile result, not duplicates
    oauth_results = [r for r in results if r.source == "oauth_profile"]
    assert len(oauth_results) == 1
