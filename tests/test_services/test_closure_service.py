"""Unit tests for closure_service — registry lookup and closure request management."""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.db.models import (
    DiscoveredAccount,
    LinkedEmail,
    ScanSession,
    User,
)
from account_hub.security.encryption import encrypt_token
from account_hub.security.hashing import hash_password
from account_hub.services.closure_service import (
    AccountNotFoundError,
    RequestNotFoundError,
    complete_closure,
    get_closure_info,
    get_closure_request,
    list_closure_requests,
    list_registry_services,
    request_closure,
)

# --- Registry lookup tests (no DB needed) ---


def test_get_closure_info_known_service():
    info = get_closure_info("Google Account")
    assert info.service_name == "Google Account"
    assert info.deletion_url is not None
    assert info.method == "web"
    assert info.difficulty in ("easy", "medium", "hard")


def test_get_closure_info_case_insensitive():
    info = get_closure_info("google account")
    assert info.deletion_url is not None


def test_get_closure_info_unknown_service():
    info = get_closure_info("SomeRandomService123")
    assert info.method == "manual"
    assert info.difficulty == "unknown"
    assert info.deletion_url is None


def test_list_registry_services():
    services = list_registry_services()
    assert len(services) >= 30
    assert "Google Account" in services
    assert "Twitter" in services
    assert "Facebook" in services


def test_registry_entries_have_required_fields():
    for service_name in list_registry_services():
        info = get_closure_info(service_name)
        assert info.deletion_url is not None
        assert info.method in ("web", "api", "email", "manual")
        assert info.difficulty in ("easy", "medium", "hard")


# --- DB-backed closure request tests ---


async def _setup_user_with_scan(db: AsyncSession):
    """Create a user, linked email, scan session, and discovered account."""
    uname = f"closeuser_{uuid.uuid4().hex[:6]}"
    user = User(
        username=uname,
        email=f"{uname}@test.com",
        email_verified=True,
        password_hash=hash_password("pass"),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    linked = LinkedEmail(
        user_id=user.id, email_address="user@gmail.com", provider="google",
        access_token_enc=encrypt_token("tok"), is_verified=True,
    )
    db.add(linked)
    await db.commit()

    scan = ScanSession(user_id=user.id, status="completed", emails_scanned=1, accounts_found=1)
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    account = DiscoveredAccount(
        scan_session_id=scan.id, email_address="user@gmail.com",
        service_name="Twitter", source="hibp_breach", confidence="confirmed",
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    return user, account


@pytest.mark.asyncio
async def test_request_closure_creates_request(db_session: AsyncSession):
    user, account = await _setup_user_with_scan(db_session)
    closure = await request_closure(db_session, user.id, account.id)
    assert closure.service_name == "Twitter"
    assert closure.status == "pending"
    assert closure.method == "web"
    assert closure.deletion_url is not None


@pytest.mark.asyncio
async def test_request_closure_unknown_account(db_session: AsyncSession):
    user, _ = await _setup_user_with_scan(db_session)
    with pytest.raises(AccountNotFoundError):
        await request_closure(db_session, user.id, uuid.uuid4())


@pytest.mark.asyncio
async def test_request_closure_wrong_user(db_session: AsyncSession):
    _, account = await _setup_user_with_scan(db_session)
    oname = f"other_{uuid.uuid4().hex[:6]}"
    other_user = User(
        username=oname,
        email=f"{oname}@test.com",
        email_verified=True,
        password_hash=hash_password("p"),
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    with pytest.raises(AccountNotFoundError):
        await request_closure(db_session, other_user.id, account.id)


@pytest.mark.asyncio
async def test_complete_closure(db_session: AsyncSession):
    user, account = await _setup_user_with_scan(db_session)
    closure = await request_closure(db_session, user.id, account.id)
    assert closure.status == "pending"

    completed = await complete_closure(db_session, user.id, closure.id)
    assert completed.status == "completed"
    assert completed.completed_at is not None


@pytest.mark.asyncio
async def test_complete_closure_not_found(db_session: AsyncSession):
    user, _ = await _setup_user_with_scan(db_session)
    with pytest.raises(RequestNotFoundError):
        await complete_closure(db_session, user.id, uuid.uuid4())


@pytest.mark.asyncio
async def test_list_closure_requests(db_session: AsyncSession):
    user, account = await _setup_user_with_scan(db_session)
    await request_closure(db_session, user.id, account.id)

    requests = await list_closure_requests(db_session, user.id)
    assert len(requests) == 1
    assert requests[0].service_name == "Twitter"


@pytest.mark.asyncio
async def test_list_closure_requests_empty(db_session: AsyncSession):
    user, _ = await _setup_user_with_scan(db_session)
    requests = await list_closure_requests(db_session, user.id)
    assert requests == []


@pytest.mark.asyncio
async def test_get_closure_request(db_session: AsyncSession):
    user, account = await _setup_user_with_scan(db_session)
    closure = await request_closure(db_session, user.id, account.id)

    fetched = await get_closure_request(db_session, user.id, closure.id)
    assert fetched.id == closure.id
    assert fetched.service_name == "Twitter"
