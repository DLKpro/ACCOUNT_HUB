from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.api.dependencies import get_current_user, get_db
from account_hub.api.limiter import limiter
from account_hub.db.models import User
from account_hub.services.closure_service import (
    AccountNotFoundError,
    RequestNotFoundError,
    complete_closure,
    get_closure_info,
    list_closure_requests,
    request_closure,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


# --- Response schemas ---


class ClosureInfoResponse(BaseModel):
    service_name: str
    deletion_url: str | None = None
    difficulty: str
    method: str
    notes: str


class ClosureRequestResponse(BaseModel):
    id: str
    service_name: str
    method: str
    status: str
    deletion_url: str | None = None
    requested_at: str
    completed_at: str | None = None
    notes: str | None = None


class RequestCloseBody(BaseModel):
    discovered_account_id: str


class CompleteCloseBody(BaseModel):
    request_id: str


# --- Endpoints ---


@router.post("/close", response_model=ClosureRequestResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_closure_request(
    request: Request,
    body: RequestCloseBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Request closure of a discovered third-party account."""
    try:
        account_id = uuid.UUID(body.discovered_account_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid account ID")

    try:
        closure = await request_closure(db, current_user.id, account_id)
    except AccountNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    return ClosureRequestResponse(
        id=str(closure.id),
        service_name=closure.service_name,
        method=closure.method,
        status=closure.status,
        deletion_url=closure.deletion_url,
        requested_at=closure.requested_at.isoformat() if closure.requested_at else "",
        notes=closure.notes,
    )


@router.post("/close/complete", response_model=ClosureRequestResponse)
async def mark_closure_complete(
    body: CompleteCloseBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a closure request as completed."""
    try:
        request_id = uuid.UUID(body.request_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request ID")

    try:
        closure = await complete_closure(db, current_user.id, request_id)
    except RequestNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    return ClosureRequestResponse(
        id=str(closure.id),
        service_name=closure.service_name,
        method=closure.method,
        status=closure.status,
        deletion_url=closure.deletion_url,
        requested_at=closure.requested_at.isoformat() if closure.requested_at else "",
        completed_at=closure.completed_at.isoformat() if closure.completed_at else None,
        notes=closure.notes,
    )


@router.get("/close-requests", response_model=list[ClosureRequestResponse])
async def list_requests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all closure requests for the current user."""
    requests = await list_closure_requests(db, current_user.id)
    return [
        ClosureRequestResponse(
            id=str(r.id),
            service_name=r.service_name,
            method=r.method,
            status=r.status,
            deletion_url=r.deletion_url,
            requested_at=r.requested_at,
            completed_at=r.completed_at,
            notes=r.notes,
        )
        for r in requests
    ]


@router.get("/close-info/{service_name}", response_model=ClosureInfoResponse)
async def close_info(service_name: str):
    """Get deletion instructions for a service."""
    info = get_closure_info(service_name)
    return ClosureInfoResponse(
        service_name=info.service_name,
        deletion_url=info.deletion_url,
        difficulty=info.difficulty,
        method=info.method,
        notes=info.notes,
    )
