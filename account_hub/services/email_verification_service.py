from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.db.models import EmailVerificationToken, User

security_logger = logging.getLogger("account_hub.security")

VERIFICATION_TOKEN_EXPIRY_HOURS = 24


class VerificationError(Exception):
    pass


class InvalidVerificationTokenError(VerificationError):
    pass


class AlreadyVerifiedError(VerificationError):
    pass


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_verification_token(db: AsyncSession, user_id: str) -> str:
    """Generate an email verification token. Returns the plaintext token."""
    # Invalidate any existing unused tokens
    existing = await db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.used.is_(False),
        )
    )
    for old in existing.scalars():
        old.used = True
    await db.flush()

    plaintext = secrets.token_urlsafe(32)
    token = EmailVerificationToken(
        user_id=user_id,
        token_hash=_hash_token(plaintext),
        expires_at=datetime.now(datetime.UTC) + timedelta(hours=VERIFICATION_TOKEN_EXPIRY_HOURS),
    )
    db.add(token)
    await db.commit()

    security_logger.info("SECURITY_EVENT: verification_token_created user=%s", user_id)
    return plaintext


async def verify_email(db: AsyncSession, token: str) -> User:
    """Validate a verification token and mark the user's email as verified."""
    token_hash = _hash_token(token)
    result = await db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.used.is_(False),
            EmailVerificationToken.expires_at > datetime.now(datetime.UTC),
        )
    )
    vt = result.scalar_one_or_none()
    if vt is None:
        security_logger.warning("SECURITY_EVENT: verification_invalid_token")
        raise InvalidVerificationTokenError("Invalid or expired verification token")

    vt.used = True

    user_result = await db.execute(select(User).where(User.id == vt.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise InvalidVerificationTokenError("User no longer exists")

    if user.email_verified:
        raise AlreadyVerifiedError("Email is already verified")

    user.email_verified = True
    await db.commit()

    security_logger.info("SECURITY_EVENT: email_verified user=%s", user.id)
    return user
