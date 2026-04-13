from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.db.models import ClosureRequest, DiscoveredAccount

_REGISTRY_PATH = Path(__file__).parent.parent / "data" / "deletion_registry.json"
_registry_cache: dict[str, dict] | None = None


class ClosureServiceError(Exception):
    pass


class AccountNotFoundError(ClosureServiceError):
    pass


class RequestNotFoundError(ClosureServiceError):
    pass


@dataclass
class ClosureInfo:
    service_name: str
    deletion_url: str | None
    difficulty: str
    method: str
    notes: str


@dataclass
class ClosureRequestInfo:
    id: uuid.UUID
    service_name: str
    method: str
    status: str
    deletion_url: str | None
    requested_at: str
    completed_at: str | None
    notes: str | None


def _load_registry() -> dict[str, dict]:
    global _registry_cache
    if _registry_cache is None:
        if _REGISTRY_PATH.exists():
            _registry_cache = json.loads(_REGISTRY_PATH.read_text())
        else:
            _registry_cache = {}
    return _registry_cache


def get_closure_info(service_name: str) -> ClosureInfo:
    """Look up deletion instructions for a service from the registry."""
    registry = _load_registry()

    # Try exact match first, then case-insensitive
    entry = registry.get(service_name)
    if entry is None:
        for key, val in registry.items():
            if key.lower() == service_name.lower():
                entry = val
                break

    if entry is None:
        return ClosureInfo(
            service_name=service_name,
            deletion_url=None,
            difficulty="unknown",
            method="manual",
            notes="No deletion instructions available. You may need to visit the service directly.",
        )

    return ClosureInfo(
        service_name=service_name,
        deletion_url=entry.get("deletion_url"),
        difficulty=entry.get("difficulty", "unknown"),
        method=entry.get("method", "web"),
        notes=entry.get("notes", ""),
    )


def list_registry_services() -> list[str]:
    """Return all service names in the deletion registry."""
    return list(_load_registry().keys())


async def request_closure(
    db: AsyncSession,
    user_id: uuid.UUID,
    discovered_account_id: uuid.UUID,
) -> ClosureRequest:
    """Create a closure request for a discovered account."""
    # Verify the discovered account belongs to this user (via scan session)
    result = await db.execute(
        select(DiscoveredAccount)
        .join(DiscoveredAccount.scan_session)
        .where(
            DiscoveredAccount.id == discovered_account_id,
            DiscoveredAccount.scan_session.has(user_id=user_id),
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise AccountNotFoundError("Discovered account not found")

    info = get_closure_info(account.service_name)

    closure = ClosureRequest(
        user_id=user_id,
        discovered_account_id=discovered_account_id,
        service_name=account.service_name,
        method=info.method,
        status="pending",
        deletion_url=info.deletion_url,
        notes=info.notes,
    )
    db.add(closure)
    await db.commit()
    await db.refresh(closure)
    return closure


async def complete_closure(
    db: AsyncSession, user_id: uuid.UUID, request_id: uuid.UUID
) -> ClosureRequest:
    """Mark a closure request as completed."""
    closure = await _get_request(db, user_id, request_id)
    closure.status = "completed"
    closure.completed_at = datetime.now(timezone.utc)  # noqa: UP017
    await db.commit()
    await db.refresh(closure)
    return closure


async def list_closure_requests(
    db: AsyncSession, user_id: uuid.UUID
) -> list[ClosureRequestInfo]:
    """List all closure requests for a user."""
    result = await db.execute(
        select(ClosureRequest)
        .where(ClosureRequest.user_id == user_id)
        .order_by(ClosureRequest.requested_at.desc())
    )
    requests = result.scalars().all()
    return [
        ClosureRequestInfo(
            id=r.id,
            service_name=r.service_name,
            method=r.method,
            status=r.status,
            deletion_url=r.deletion_url,
            requested_at=r.requested_at.isoformat() if r.requested_at else "",
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
            notes=r.notes,
        )
        for r in requests
    ]


async def get_closure_request(
    db: AsyncSession, user_id: uuid.UUID, request_id: uuid.UUID
) -> ClosureRequestInfo:
    """Get a single closure request."""
    r = await _get_request(db, user_id, request_id)
    return ClosureRequestInfo(
        id=r.id,
        service_name=r.service_name,
        method=r.method,
        status=r.status,
        deletion_url=r.deletion_url,
        requested_at=r.requested_at.isoformat() if r.requested_at else "",
        completed_at=r.completed_at.isoformat() if r.completed_at else None,
        notes=r.notes,
    )


async def _get_request(
    db: AsyncSession, user_id: uuid.UUID, request_id: uuid.UUID
) -> ClosureRequest:
    result = await db.execute(
        select(ClosureRequest).where(
            ClosureRequest.id == request_id,
            ClosureRequest.user_id == user_id,
        )
    )
    closure = result.scalar_one_or_none()
    if closure is None:
        raise RequestNotFoundError("Closure request not found")
    return closure
