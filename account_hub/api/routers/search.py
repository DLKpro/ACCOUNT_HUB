from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.api.dependencies import get_current_user, get_db
from account_hub.api.limiter import limiter
from account_hub.api.utils import parse_uuid
from account_hub.db.models import User
from account_hub.services.discovery_service import (
    ScanNotFoundError,
    get_scan_history,
    get_scan_results,
    get_scan_session,
    start_scan,
)
from account_hub.services.export_service import export_to_csv

router = APIRouter(prefix="/search", tags=["search"])


# --- Response schemas ---


class ScanStartResponse(BaseModel):
    scan_session_id: str
    status: str


class DiscoveredAccountResponse(BaseModel):
    id: str
    email_address: str
    service_name: str
    service_domain: str | None = None
    source: str
    confidence: str
    breach_date: str | None = None
    discovered_at: str | None = None


class ScanDetailResponse(BaseModel):
    id: str
    status: str
    emails_scanned: int
    accounts_found: int
    started_at: str | None = None
    completed_at: str | None = None
    results: list[DiscoveredAccountResponse] = []


class ScanSummaryResponse(BaseModel):
    id: str
    status: str
    emails_scanned: int
    accounts_found: int
    created_at: str | None = None


# --- Endpoints ---


@router.post("", response_model=ScanStartResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def create_scan(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a new discovery scan across all linked emails."""
    if not current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address before running scans",
        )
    session = await start_scan(db, current_user.id)
    return ScanStartResponse(
        scan_session_id=str(session.id),
        status=session.status,
    )


@router.get("/history", response_model=list[ScanSummaryResponse])
async def scan_history(
    limit: int = 10,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List past scan sessions."""
    sessions = await get_scan_history(db, current_user.id, limit=limit, offset=offset)
    return [
        ScanSummaryResponse(
            id=str(s.id),
            status=s.status,
            emails_scanned=s.emails_scanned,
            accounts_found=s.accounts_found,
            created_at=s.created_at.isoformat() if s.created_at else None,
        )
        for s in sessions
    ]


@router.get("/{session_id}", response_model=ScanDetailResponse)
async def get_scan(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get scan session details and results."""
    sid = parse_uuid(session_id, "session ID")

    try:
        session = await get_scan_session(db, current_user.id, sid)
    except ScanNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")

    results = await get_scan_results(db, session.id)

    return ScanDetailResponse(
        id=str(session.id),
        status=session.status,
        emails_scanned=session.emails_scanned,
        accounts_found=session.accounts_found,
        started_at=session.started_at.isoformat() if session.started_at else None,
        completed_at=session.completed_at.isoformat() if session.completed_at else None,
        results=[
            DiscoveredAccountResponse(
                id=str(a.id),
                email_address=a.email_address,
                service_name=a.service_name,
                service_domain=a.service_domain,
                source=a.source,
                confidence=a.confidence,
                breach_date=str(a.breach_date) if a.breach_date else None,
                discovered_at=a.discovered_at.isoformat() if a.discovered_at else None,
            )
            for a in results
        ],
    )


@router.get("/{session_id}/export")
async def export_scan(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export scan results as CSV."""
    sid = parse_uuid(session_id, "session ID")

    try:
        await get_scan_session(db, current_user.id, sid)
    except ScanNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")

    results = await get_scan_results(db, sid)
    csv_content = export_to_csv(results)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="accounthub_scan_{session_id}.csv"'
        },
    )
