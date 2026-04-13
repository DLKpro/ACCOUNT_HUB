from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import List, Optional

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.db.models import LinkedEmail
from account_hub.oauth.providers import get_provider
from account_hub.security.encryption import decrypt_token


class EmailServiceError(Exception):
    pass


class EmailNotFound(EmailServiceError):
    pass


@dataclass
class LinkedEmailInfo:
    id: uuid.UUID
    email_address: str
    provider: str
    is_verified: bool
    linked_at: str


async def list_linked_emails(db: AsyncSession, user_id: uuid.UUID) -> List[LinkedEmailInfo]:
    """Return all linked emails for a user."""
    result = await db.execute(
        select(LinkedEmail)
        .where(LinkedEmail.user_id == user_id)
        .order_by(LinkedEmail.linked_at)
    )
    emails = result.scalars().all()
    return [
        LinkedEmailInfo(
            id=e.id,
            email_address=e.email_address,
            provider=e.provider,
            is_verified=e.is_verified,
            linked_at=e.linked_at.isoformat() if e.linked_at else "",
        )
        for e in emails
    ]


async def get_linked_email(
    db: AsyncSession, user_id: uuid.UUID, email_id: uuid.UUID
) -> LinkedEmail:
    """Get a specific linked email, ensuring it belongs to the user."""
    result = await db.execute(
        select(LinkedEmail).where(
            LinkedEmail.id == email_id,
            LinkedEmail.user_id == user_id,
        )
    )
    email = result.scalar_one_or_none()
    if email is None:
        raise EmailNotFound("Linked email not found")
    return email


async def unlink_email(db: AsyncSession, user_id: uuid.UUID, email_id: uuid.UUID) -> None:
    """Remove a linked email. Attempts to revoke the OAuth token with the provider first."""
    email = await get_linked_email(db, user_id, email_id)

    # Best-effort token revocation
    await _try_revoke_token(email)

    await db.execute(delete(LinkedEmail).where(LinkedEmail.id == email_id))
    await db.commit()


async def _try_revoke_token(email: LinkedEmail) -> None:
    """Attempt to revoke the OAuth token with the provider. Failures are silently ignored."""
    if not email.access_token_enc:
        return

    try:
        provider = get_provider(email.provider)
    except ValueError:
        return

    if not provider.revoke_url:
        return

    try:
        access_token = decrypt_token(email.access_token_enc)
        async with httpx.AsyncClient() as client:
            await client.post(
                provider.revoke_url,
                data={"token": access_token},
                timeout=10.0,
            )
    except Exception:
        pass  # Best-effort — don't fail the unlink if revocation fails
