from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.config import (
    LOCKOUT_DURATION_MINUTES,
    MAX_FAILED_LOGIN_ATTEMPTS,
    MIN_PASSWORD_LENGTH,
)
from account_hub.db.models import User
from account_hub.security.hashing import hash_password, verify_password
from account_hub.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
)

security_logger = logging.getLogger("account_hub.security")

USERNAME_PATTERN = re.compile(r"^[a-z0-9_]{3,64}$")
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class UserServiceError(Exception):
    pass


class UsernameInvalidError(UserServiceError):
    pass


class EmailInvalidError(UserServiceError):
    pass


class EmailTakenError(UserServiceError):
    pass


class UsernameTakenError(UserServiceError):
    pass


class PasswordTooShortError(UserServiceError):
    pass


class AccountLockedError(UserServiceError):
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
    db: AsyncSession, username: str, email: str, password: str
) -> tuple[User, TokenPair]:
    """Create a new user and return the user + token pair."""
    username = username.lower().strip()
    email = email.lower().strip()

    if not USERNAME_PATTERN.match(username):
        raise UsernameInvalidError(
            "Username must be 3-64 characters, lowercase letters, numbers, and underscores only"
        )

    if not EMAIL_PATTERN.match(email):
        raise EmailInvalidError("Please enter a valid email address")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordTooShortError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
        )

    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none() is not None:
        raise UsernameTakenError(f"Username '{username}' is already taken")

    existing_email = await db.execute(select(User).where(User.email == email))
    if existing_email.scalar_one_or_none() is not None:
        raise EmailTakenError("An account with this email already exists")

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    security_logger.info("SECURITY_EVENT: registration user=%s", user.id)

    tokens = TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )
    return user, tokens


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> tuple[User, TokenPair]:
    """Verify credentials and return the user + token pair.

    The `username` parameter accepts either a username or email address.
    """
    identifier = username.lower().strip()

    # Try username first, then email
    if "@" in identifier:
        result = await db.execute(select(User).where(User.email == identifier))
    else:
        result = await db.execute(select(User).where(User.username == identifier))
    user = result.scalar_one_or_none()

    if user is None:
        raise InvalidCredentialsError("Invalid username or password")

    # Check account lockout
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):  # noqa: UP017
        security_logger.warning(
            "SECURITY_EVENT: login_blocked_locked user=%s", user.id
        )
        raise AccountLockedError(
            "Account is temporarily locked due to too many failed login attempts. "
            "Please try again later."
        )

    if not verify_password(password, user.password_hash):
        # Increment failed attempts
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(  # noqa: UP017
                minutes=LOCKOUT_DURATION_MINUTES
            )
            security_logger.warning(
                "SECURITY_EVENT: account_locked user=%s attempts=%d",
                user.id, user.failed_login_attempts,
            )
        else:
            security_logger.info(
                "SECURITY_EVENT: login_failed user=%s attempts=%d",
                user.id, user.failed_login_attempts,
            )
        await db.commit()
        raise InvalidCredentialsError("Invalid username or password")

    if not user.is_active:
        raise InvalidCredentialsError("Account is deactivated")

    # Reset failed attempts on successful login
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()

    security_logger.info("SECURITY_EVENT: login_success user=%s", user.id)

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
        security_logger.info("SECURITY_EVENT: token_refresh_failed reason=invalid_token")
        raise InvalidTokenError("Invalid or expired refresh token")

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None:
        security_logger.info("SECURITY_EVENT: token_refresh_failed reason=user_not_found")
        raise InvalidTokenError("User not found or inactive")

    security_logger.info("SECURITY_EVENT: token_refresh user=%s", user.id)
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


async def delete_account(db: AsyncSession, user: User, password: str) -> None:
    """Delete a user account after password confirmation. Cascades to all related data."""
    if not verify_password(password, user.password_hash):
        security_logger.warning("SECURITY_EVENT: account_delete_failed user=%s", user.id)
        raise InvalidCredentialsError("Incorrect password")

    # Revoke all OAuth tokens before cascade deletion destroys the encrypted tokens
    from account_hub.db.models import LinkedEmail
    from account_hub.services.email_service import try_revoke_token
    result = await db.execute(
        select(LinkedEmail).where(LinkedEmail.user_id == user.id)
    )
    for linked_email in result.scalars().all():
        await try_revoke_token(linked_email)

    security_logger.warning("SECURITY_EVENT: account_deleted user=%s", user.id)
    await db.delete(user)
    await db.commit()
