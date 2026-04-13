from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.db.models import DiscoveredAccount, LinkedEmail, ScanSession
from account_hub.discovery.base import BaseScanner, DiscoveredAccountResult
from account_hub.discovery.gravatar import GravatarScanner
from account_hub.discovery.hibp import HIBPBreachScanner
from account_hub.discovery.oauth_profile import OAuthProfileScanner


class DiscoveryServiceError(Exception):
    pass


class ScanNotFoundError(DiscoveryServiceError):
    pass


def _get_scanners(provider: str) -> list[BaseScanner]:
    """Build the list of scanners for a given email provider."""
    scanners: list[BaseScanner] = [
        OAuthProfileScanner(provider),
        GravatarScanner(),
        HIBPBreachScanner(),
    ]
    return [s for s in scanners if s.is_available()]


async def start_scan(db: AsyncSession, user_id: uuid.UUID) -> ScanSession:
    """Create a scan session and run discovery across all linked emails."""
    # Get linked emails
    result = await db.execute(
        select(LinkedEmail).where(
            LinkedEmail.user_id == user_id,
            LinkedEmail.is_verified.is_(True),
        )
    )
    emails = result.scalars().all()

    # Create scan session
    session = ScanSession(
        user_id=user_id,
        status="running",
        emails_scanned=len(emails),
        started_at=datetime.now(timezone.utc),  # noqa: UP017
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    if not emails:
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)  # noqa: UP017
        await db.commit()
        return session

    # Run scanners
    all_results: list[DiscoveredAccountResult] = []
    for email in emails:
        scanners = _get_scanners(email.provider)
        tasks = [scanner.scan(email.email_address) for scanner in scanners]
        scanner_results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in scanner_results:
            if isinstance(res, Exception):
                continue  # Skip failed scanners
            all_results.extend(res)

    # Deduplicate and persist
    seen = set()
    for r in all_results:
        key = (r.email_address, r.service_name, r.source)
        if key in seen:
            continue
        seen.add(key)

        account = DiscoveredAccount(
            scan_session_id=session.id,
            email_address=r.email_address,
            service_name=r.service_name,
            service_domain=r.service_domain,
            source=r.source,
            source_detail=r.source_detail,
            confidence=r.confidence,
        )
        db.add(account)

    session.status = "completed"
    session.accounts_found = len(seen)
    session.completed_at = datetime.now(timezone.utc)  # noqa: UP017
    await db.commit()
    await db.refresh(session)

    return session


async def get_scan_session(
    db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID
) -> ScanSession:
    """Get a scan session by ID, ensuring it belongs to the user."""
    result = await db.execute(
        select(ScanSession).where(
            ScanSession.id == session_id,
            ScanSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise ScanNotFoundError("Scan session not found")
    return session


async def get_scan_results(
    db: AsyncSession, session_id: uuid.UUID
) -> list[DiscoveredAccount]:
    """Get all discovered accounts for a scan session."""
    result = await db.execute(
        select(DiscoveredAccount)
        .where(DiscoveredAccount.scan_session_id == session_id)
        .order_by(DiscoveredAccount.email_address, DiscoveredAccount.service_name)
    )
    return list(result.scalars().all())


async def get_scan_history(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 10, offset: int = 0
) -> list[ScanSession]:
    """Get past scan sessions for a user, newest first."""
    result = await db.execute(
        select(ScanSession)
        .where(ScanSession.user_id == user_id)
        .order_by(ScanSession.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
