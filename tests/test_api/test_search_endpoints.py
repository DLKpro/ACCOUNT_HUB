"""Integration tests for search/discovery API endpoints.

Tests the full stack: HTTP → search router → discovery service → scanners →
DB models, combined with auth (JWT) and linked emails from previous phases.
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from account_hub.db.models import LinkedEmail
from account_hub.security.encryption import encrypt_token


async def _register(client: AsyncClient, test_engine, username: str = None) -> str:
    """Register, verify email, and return access token."""
    uname = username or f"user_{uuid.uuid4().hex[:8]}"
    resp = await client.post("/auth/register", json={
        "username": uname,
        "email": f"{uname}@test.com",
        "password": "testpass1",
    })
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    # Mark email as verified so scans work
    await _verify_user(test_engine, token)
    return token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _verify_user(test_engine, token: str):
    """Mark the user as email-verified in the DB."""
    from jose import jwt as jose_jwt

    from account_hub.config import settings
    from account_hub.db.models import User

    payload = jose_jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    user_id = uuid.UUID(payload["sub"])
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one()
        user.email_verified = True
        await session.commit()


async def _add_linked_email(
    test_engine, token: str, email: str, provider: str = "google"
):
    """Directly insert a linked email into the DB (bypasses OAuth flow)."""
    from jose import jwt as jose_jwt

    from account_hub.config import settings

    payload = jose_jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    user_id = uuid.UUID(payload["sub"])

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        linked = LinkedEmail(
            user_id=user_id,
            email_address=email,
            provider=provider,
            access_token_enc=encrypt_token("fake-token"),
            is_verified=True,
        )
        session.add(linked)
        await session.commit()


# --- Scan creation ---


@pytest.mark.asyncio
async def test_create_scan_no_emails(client: AsyncClient, test_engine):
    token = await _register(client, test_engine)
    resp = await client.post("/search", headers=_auth(token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"
    assert "scan_session_id" in data


@pytest.mark.asyncio
async def test_create_scan_with_linked_email(client: AsyncClient, test_engine):
    token = await _register(client, test_engine, "scanwithmail")
    await _add_linked_email(test_engine, token, "user@gmail.com", "google")

    resp = await client.post("/search", headers=_auth(token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"

    # Fetch results
    sid = data["scan_session_id"]
    detail = await client.get(f"/search/{sid}", headers=_auth(token))
    assert detail.status_code == 200
    d = detail.json()
    assert d["emails_scanned"] == 1
    assert d["accounts_found"] >= 1
    assert any(r["source"] == "oauth_profile" for r in d["results"])


@pytest.mark.asyncio
async def test_create_scan_requires_auth(client: AsyncClient):
    resp = await client.post("/search")
    assert resp.status_code in (401, 403)


# --- Get scan details ---


@pytest.mark.asyncio
async def test_get_scan_detail(client: AsyncClient, test_engine):
    token = await _register(client, test_engine)
    create = await client.post("/search", headers=_auth(token))
    sid = create.json()["scan_session_id"]

    resp = await client.get(f"/search/{sid}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == sid
    assert resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_get_scan_not_found(client: AsyncClient, test_engine):
    token = await _register(client, test_engine)
    resp = await client.get(f"/search/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_scan_wrong_user(client: AsyncClient, test_engine):
    token1 = await _register(client, test_engine, "scanowner2")
    token2 = await _register(client, test_engine, "scanother2")

    create = await client.post("/search", headers=_auth(token1))
    sid = create.json()["scan_session_id"]

    resp = await client.get(f"/search/{sid}", headers=_auth(token2))
    assert resp.status_code == 404


# --- Scan history ---


@pytest.mark.asyncio
async def test_scan_history(client: AsyncClient, test_engine):
    token = await _register(client, test_engine)
    await client.post("/search", headers=_auth(token))
    await client.post("/search", headers=_auth(token))

    resp = await client.get("/search/history", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_scan_history_empty(client: AsyncClient, test_engine):
    token = await _register(client, test_engine)
    resp = await client.get("/search/history", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_scan_history_scoped_to_user(client: AsyncClient, test_engine):
    token1 = await _register(client, test_engine, "histuser1")
    token2 = await _register(client, test_engine, "histuser2")

    await client.post("/search", headers=_auth(token1))
    await client.post("/search", headers=_auth(token1))
    await client.post("/search", headers=_auth(token2))

    h1 = await client.get("/search/history", headers=_auth(token1))
    h2 = await client.get("/search/history", headers=_auth(token2))
    assert len(h1.json()) == 2
    assert len(h2.json()) == 1


# --- Export ---


@pytest.mark.asyncio
async def test_export_csv(client: AsyncClient, test_engine):
    token = await _register(client, test_engine, "exportuser")
    await _add_linked_email(test_engine, token, "export@gmail.com", "google")

    create = await client.post("/search", headers=_auth(token))
    sid = create.json()["scan_session_id"]

    resp = await client.get(f"/search/{sid}/export", headers=_auth(token))
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "email_address" in resp.text  # CSV header
    assert "export@gmail.com" in resp.text


@pytest.mark.asyncio
async def test_export_empty_scan(client: AsyncClient, test_engine):
    token = await _register(client, test_engine)
    create = await client.post("/search", headers=_auth(token))
    sid = create.json()["scan_session_id"]

    resp = await client.get(f"/search/{sid}/export", headers=_auth(token))
    assert resp.status_code == 200
    assert "email_address" in resp.text  # Header still present
    lines = resp.text.strip().split("\n")
    assert len(lines) == 1  # Header only


@pytest.mark.asyncio
async def test_export_not_found(client: AsyncClient, test_engine):
    token = await _register(client, test_engine)
    resp = await client.get(f"/search/{uuid.uuid4()}/export", headers=_auth(token))
    assert resp.status_code == 404


# --- Full flow: register → link email → scan → view results → export ---


@pytest.mark.asyncio
async def test_full_discovery_flow(client: AsyncClient, test_engine):
    """Integration: register → link email → scan → get results → export CSV."""
    # Register
    token = await _register(client, test_engine, "fullscanuser")

    # Link an email (direct DB insert since we can't do real OAuth)
    await _add_linked_email(test_engine, token, "full@gmail.com", "google")

    # Verify email is linked
    emails = await client.get("/emails", headers=_auth(token))
    assert len(emails.json()) == 2  # primary + linked

    # Run scan
    scan = await client.post("/search", headers=_auth(token))
    assert scan.status_code == 201
    sid = scan.json()["scan_session_id"]

    # Get results
    detail = await client.get(f"/search/{sid}", headers=_auth(token))
    assert detail.status_code == 200
    d = detail.json()
    assert d["status"] == "completed"
    assert d["emails_scanned"] == 1
    assert d["accounts_found"] >= 1

    # Check history
    history = await client.get("/search/history", headers=_auth(token))
    assert len(history.json()) == 1

    # Export
    export = await client.get(f"/search/{sid}/export", headers=_auth(token))
    assert export.status_code == 200
    assert "full@gmail.com" in export.text
    assert "Google Account" in export.text
