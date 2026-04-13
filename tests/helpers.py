"""Shared test helpers for creating users, emails, and auth tokens."""
from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from account_hub.db.models import LinkedEmail, User
from account_hub.security.encryption import encrypt_token
from account_hub.security.hashing import hash_password


async def create_test_user(db: AsyncSession, username: str = "testuser") -> User:
    user = User(
        username=username,
        email=f"{username}@test.com",
        email_verified=True,
        password_hash=hash_password("pass"),
    )
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


async def register_user(
    client: AsyncClient,
    username: str | None = None,
    *,
    verified: bool = False,
    test_engine=None,
) -> str:
    """Register a user via the API and return the access token.

    If verified=True and test_engine is provided, the user's email is
    marked as verified in the database (needed for scan-gated features).
    """
    uname = username or f"user_{uuid.uuid4().hex[:8]}"
    resp = await client.post("/auth/register", json={
        "username": uname, "email": f"{uname}@test.com", "password": "testpass1",
    })
    assert resp.status_code == 201
    token = resp.json()["access_token"]

    if verified and test_engine:
        from jose import jwt as jose_jwt

        from account_hub.config import settings

        payload = jose_jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id = uuid.UUID(payload["sub"])
        factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one()
            user.email_verified = True
            await session.commit()

    return token


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
