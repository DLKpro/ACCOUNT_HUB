"""Shared test helpers for creating users, emails, and auth tokens."""
from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.db.models import LinkedEmail, User
from account_hub.security.encryption import encrypt_token
from account_hub.security.hashing import hash_password


async def create_test_user(db: AsyncSession, username: str = "testuser") -> User:
    user = User(username=username, password_hash=hash_password("pass"))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_linked_email(
    db: AsyncSession,
    user: User,
    email: str = "test@gmail.com",
    provider: str = "google",
) -> LinkedEmail:
    linked = LinkedEmail(
        user_id=user.id,
        email_address=email,
        provider=provider,
        access_token_enc=encrypt_token("fake-token"),
        is_verified=True,
    )
    db.add(linked)
    await db.commit()
    await db.refresh(linked)
    return linked


async def register_user(client: AsyncClient, username: str | None = None) -> str:
    """Register a user via the API and return the access token."""
    uname = username or f"user_{uuid.uuid4().hex[:8]}"
    resp = await client.post("/auth/register", json={"username": uname, "password": "testpass1"})
    assert resp.status_code == 201
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
