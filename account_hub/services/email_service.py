from __future__ import annotations

import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.db.models import LinkedEmail
from account_hub.oauth.providers import get_provider
from account_hub.security.encryption import decrypt_token


class EmailServiceError(Exception):
    pass


class EmailNotFoundError(EmailServiceError):
    pass


@dataclass
class LinkedEmailInfo:
    id: uuid.UUID
    email_address: str
    provider: str
    is_verified: bool
    linked_at: str


async def list_linked_emails(db: AsyncSession, user_id: uuid.UUID) -> list[LinkedEmailInfo]:
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
        raise EmailNotFoundError("Linked email not found")
    return email


async def unlink_email(db: AsyncSession, user_id: uuid.UUID, email_id: uuid.UUID) -> None:
    """Remove a linked email. Attempts to revoke the OAuth token with the provider first."""
    email = await get_linked_email(db, user_id, email_id)

    # Best-effort token revocation
    await try_revoke_token(email)

    await db.execute(delete(LinkedEmail).where(LinkedEmail.id == email_id))
    await db.commit()


async def try_revoke_token(email: LinkedEmail) -> None:
    """Attempt to revoke the OAuth token with the provider. Failures are silently ignored."""
    if not email.access_token_enc:
        return

    try:
        provider = get_provider(email.provider)
    except ValueError:
        return

    try:
        access_token = decrypt_token(email.access_token_enc)
        refresh_token = decrypt_token(email.refresh_token_enc) if email.refresh_token_enc else None

        async with httpx.AsyncClient(timeout=10.0) as client:
            if email.provider == "apple":
                from account_hub.config import settings
                from account_hub.oauth.apple_jwt import generate_apple_client_secret
                client_secret = generate_apple_client_secret(
                    settings.apple_team_id, settings.apple_client_id,
                    settings.apple_key_id, settings.apple_private_key_path,
                )
                token_to_revoke = refresh_token or access_token
                hint = "refresh_token" if refresh_token else "access_token"
                await client.post(
                    provider.revoke_url,
                    data={
                        "client_id": settings.apple_client_id,
                        "client_secret": client_secret,
                        "token": token_to_revoke,
                        "token_type_hint": hint,
                    },
                )
            elif email.provider == "meta":
                await client.delete(
                    "https://graph.facebook.com/v19.0/me/permissions",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            elif provider.revoke_url:
                await client.post(
                    provider.revoke_url,
                    data={"token": access_token},
                )
    except Exception:
        pass  # Best-effort — don't fail the unlink if revocation fails
