"""Integration tests for account closure API endpoints.

Tests the full stack: auth (register/JWT) → linked emails → discovery scan →
closure requests → completion. Exercises all 5 phases working together.
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from account_hub.db.models import LinkedEmail
from account_hub.security.encryption import encrypt_token


async def _register(client: AsyncClient, username: str = None) -> str:
    uname = username or f"user_{uuid.uuid4().hex[:8]}"
    resp = await client.post("/auth/register", json={"username": uname, "password": "pass"})
    assert resp.status_code == 201
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _add_linked_email(test_engine, token: str, email: str, provider: str = "google"):
    from jose import jwt as jose_jwt
    from account_hub.config import settings
    payload = jose_jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    user_id = uuid.UUID(payload["sub"])
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        linked = LinkedEmail(
            user_id=user_id, email_address=email, provider=provider,
            access_token_enc=encrypt_token("fake-token"), is_verified=True,
        )
        session.add(linked)
        await session.commit()


async def _scan_and_get_account_id(client: AsyncClient, token: str) -> str:
    """Run a scan and return the first discovered account ID."""
    scan = await client.post("/search", headers=_auth(token))
    sid = scan.json()["scan_session_id"]
    detail = await client.get(f"/search/{sid}", headers=_auth(token))
    results = detail.json()["results"]
    assert len(results) > 0
    return results[0]["id"]


# --- Closure Info (no auth needed) ---


@pytest.mark.asyncio
async def test_close_info_known_service(client: AsyncClient):
    resp = await client.get("/accounts/close-info/Twitter")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service_name"] == "Twitter"
    assert data["deletion_url"] is not None
    assert data["method"] == "web"


@pytest.mark.asyncio
async def test_close_info_unknown_service(client: AsyncClient):
    resp = await client.get("/accounts/close-info/UnknownService999")
    assert resp.status_code == 200
    data = resp.json()
    assert data["method"] == "manual"
    assert data["deletion_url"] is None


# --- Closure Requests ---


@pytest.mark.asyncio
async def test_request_closure(client: AsyncClient, test_engine):
    token = await _register(client, "closeuser1")
    await _add_linked_email(test_engine, token, "close@gmail.com")
    account_id = await _scan_and_get_account_id(client, token)

    resp = await client.post(
        "/accounts/close",
        headers=_auth(token),
        json={"discovered_account_id": account_id},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["service_name"] == "Google Account"
    assert data["method"] == "web"


@pytest.mark.asyncio
async def test_request_closure_not_found(client: AsyncClient):
    token = await _register(client)
    resp = await client.post(
        "/accounts/close",
        headers=_auth(token),
        json={"discovered_account_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_request_closure_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/accounts/close",
        json={"discovered_account_id": str(uuid.uuid4())},
    )
    assert resp.status_code in (401, 403)


# --- List Closure Requests ---


@pytest.mark.asyncio
async def test_list_closure_requests_empty(client: AsyncClient):
    token = await _register(client)
    resp = await client.get("/accounts/close-requests", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_closure_requests_after_creating(client: AsyncClient, test_engine):
    token = await _register(client, "listclose")
    await _add_linked_email(test_engine, token, "list@gmail.com")
    account_id = await _scan_and_get_account_id(client, token)

    await client.post(
        "/accounts/close", headers=_auth(token),
        json={"discovered_account_id": account_id},
    )

    resp = await client.get("/accounts/close-requests", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# --- Complete Closure ---


@pytest.mark.asyncio
async def test_complete_closure(client: AsyncClient, test_engine):
    token = await _register(client, "completeclose")
    await _add_linked_email(test_engine, token, "complete@gmail.com")
    account_id = await _scan_and_get_account_id(client, token)

    create = await client.post(
        "/accounts/close", headers=_auth(token),
        json={"discovered_account_id": account_id},
    )
    request_id = create.json()["id"]

    resp = await client.post(
        "/accounts/close/complete", headers=_auth(token),
        json={"request_id": request_id},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["completed_at"] is not None


@pytest.mark.asyncio
async def test_complete_closure_not_found(client: AsyncClient):
    token = await _register(client)
    resp = await client.post(
        "/accounts/close/complete", headers=_auth(token),
        json={"request_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


# --- Cross-module: closure scoped to user ---


@pytest.mark.asyncio
async def test_closure_scoped_to_user(client: AsyncClient, test_engine):
    """User 2 cannot see or complete User 1's closure requests."""
    token1 = await _register(client, "closescope1")
    token2 = await _register(client, "closescope2")
    await _add_linked_email(test_engine, token1, "scope@gmail.com")
    account_id = await _scan_and_get_account_id(client, token1)

    create = await client.post(
        "/accounts/close", headers=_auth(token1),
        json={"discovered_account_id": account_id},
    )
    request_id = create.json()["id"]

    # User 2 cannot list User 1's requests
    resp = await client.get("/accounts/close-requests", headers=_auth(token2))
    assert resp.json() == []

    # User 2 cannot complete User 1's request
    resp = await client.post(
        "/accounts/close/complete", headers=_auth(token2),
        json={"request_id": request_id},
    )
    assert resp.status_code == 404


# --- Full flow: register → link → scan → close → complete → delete account ---


@pytest.mark.asyncio
async def test_full_closure_lifecycle(client: AsyncClient, test_engine):
    """Integration across all 5 phases: auth → email → scan → close → delete."""
    # Phase 2: Register
    token = await _register(client, "lifecycleuser")

    # Phase 3: Link email
    await _add_linked_email(test_engine, token, "lifecycle@gmail.com")
    emails = await client.get("/emails", headers=_auth(token))
    assert len(emails.json()) == 1

    # Phase 4: Scan
    scan = await client.post("/search", headers=_auth(token))
    assert scan.status_code == 201
    sid = scan.json()["scan_session_id"]

    detail = await client.get(f"/search/{sid}", headers=_auth(token))
    results = detail.json()["results"]
    assert len(results) >= 1
    account_id = results[0]["id"]

    # Phase 5: Request closure
    close_resp = await client.post(
        "/accounts/close", headers=_auth(token),
        json={"discovered_account_id": account_id},
    )
    assert close_resp.status_code == 201
    request_id = close_resp.json()["id"]

    # Phase 5: Mark as completed
    complete = await client.post(
        "/accounts/close/complete", headers=_auth(token),
        json={"request_id": request_id},
    )
    assert complete.json()["status"] == "completed"

    # Phase 5: Verify in closure list
    requests = await client.get("/accounts/close-requests", headers=_auth(token))
    assert len(requests.json()) == 1
    assert requests.json()[0]["status"] == "completed"

    # Phase 2+5: Delete entire account (cascading)
    delete = await client.request(
        "DELETE", "/auth/account",
        headers=_auth(token), json={"password": "pass"},
    )
    assert delete.status_code == 204

    # Token no longer works
    me = await client.get("/auth/me", headers=_auth(token))
    assert me.status_code == 401
