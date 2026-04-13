from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.db.models import User
from account_hub.security.hashing import hash_password, verify_password
from account_hub.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
)

USERNAME_PATTERN = re.compile(r"^[a-z0-9_]{3,64}$")


class UserServiceError(Exception):
    pass


class UsernameInvalidError(UserServiceError):
    pass


class UsernameTakenError(UserServiceError):
    pass


class InvalidCredentialsError(UserServiceError):
    pass


class InvalidTokenError(UserServiceError):
    pass


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str


async def register_user(
    db: AsyncSession, username: str, password: str
) -> tuple[User, TokenPair]:
    """Create a new user and return the user + token pair."""
    username = username.lower().strip()

    if not USERNAME_PATTERN.match(username):
        raise UsernameInvalidError(
            "Username must be 3-64 characters, lowercase letters, numbers, and underscores only"
        )

    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none() is not None:
        raise UsernameTakenError(f"Username '{username}' is already taken")

    user = User(
        username=username,
        password_hash=hash_password(password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    tokens = TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )
    return user, tokens


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> tuple[User, TokenPair]:
    """Verify credentials and return the user + token pair."""
    username = username.lower().strip()

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid username or password")

    if not user.is_active:
        raise InvalidCredentialsError("Account is deactivated")

    tokens = TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )
    return user, tokens


async def refresh_tokens(db: AsyncSession, refresh_token_str: str) -> TokenPair:
    """Validate a refresh token and issue a new token pair."""
    from jose import JWTError

    try:
        user_id = decode_token(refresh_token_str, expected_type="refresh")
    except JWTError:
        raise InvalidTokenError("Invalid or expired refresh token")

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise InvalidTokenError("User not found or inactive")

    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


async def delete_account(db: AsyncSession, user: User, password: str) -> None:
    """Delete a user account after password confirmation. Cascades to all related data."""
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Incorrect password")

    await db.delete(user)
    await db.commit()
