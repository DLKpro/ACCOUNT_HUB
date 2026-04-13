from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.config import MIN_PASSWORD_LENGTH
from account_hub.db.models import PasswordResetToken, User
from account_hub.security.hashing import hash_password

security_logger = logging.getLogger("account_hub.security")

RESET_TOKEN_EXPIRY_MINUTES = 30


class ResetError(Exception):
    pass


class UserNotFoundError(ResetError):
    pass


class InvalidResetTokenError(ResetError):
    pass


class PasswordTooShortError(ResetError):
    pass


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def request_password_reset(db: AsyncSession, username: str) -> str:
    """Generate a password reset token for a user. Returns the plaintext token."""
    username = username.lower().strip()

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise UserNotFoundError("User not found")

    # Invalidate any existing unused tokens for this user
    existing = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used.is_(False),
        )
    )
    for old_token in existing.scalars():
        old_token.used = True
    await db.flush()

    # Generate new token
    plaintext_token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(plaintext_token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES),
    )
    db.add(reset_token)
    await db.commit()

    security_logger.info("SECURITY_EVENT: password_reset_requested user=%s", user.id)

    return plaintext_token


async def complete_password_reset(
    db: AsyncSession, token: str, new_password: str
) -> None:
    """Validate a reset token and set the new password."""
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise PasswordTooShortError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
        )

    token_hash = _hash_token(token)
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used.is_(False),
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
    )
    reset_token = result.scalar_one_or_none()
    if reset_token is None:
        security_logger.warning("SECURITY_EVENT: password_reset_invalid_token")
        raise InvalidResetTokenError("Invalid or expired reset token")

    # Mark token as used
    reset_token.used = True
    reset_token.used_at = datetime.now(timezone.utc)

    # Update user password and clear lockout
    user_result = await db.execute(
        select(User).where(User.id == reset_token.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise InvalidResetTokenError("User no longer exists")

    user.password_hash = hash_password(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None

    await db.commit()

    security_logger.info("SECURITY_EVENT: password_reset_completed user=%s", user.id)
