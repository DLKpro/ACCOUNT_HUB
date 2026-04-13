from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.api.dependencies import get_current_user, get_db
from account_hub.api.limiter import limiter
from account_hub.api.utils import parse_uuid
from account_hub.db.models import User
from account_hub.services.email_service import (
    EmailNotFoundError,
    list_linked_emails,
    unlink_email,
)

router = APIRouter(prefix="/emails", tags=["emails"])


class LinkedEmailResponse(BaseModel):
    id: str
    email_address: str
    provider: str
    is_verified: bool
    is_primary: bool = False
    linked_at: str


@router.get("", response_model=list[LinkedEmailResponse])
async def list_emails(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    emails = await list_linked_emails(db, current_user.id)

    # Build result with primary email first
    result = [
        LinkedEmailResponse(
            id=str(current_user.id),
            email_address=current_user.email,
            provider="account",
            is_verified=current_user.email_verified,
            is_primary=True,
            linked_at=current_user.created_at.isoformat() if current_user.created_at else "",
        )
    ]
    result.extend(
        LinkedEmailResponse(
            id=str(e.id),
            email_address=e.email_address,
            provider=e.provider,
            is_verified=e.is_verified,
            linked_at=e.linked_at,
        )
        for e in emails
    )
    return result


@router.delete("/{email_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def delete_email(
    request: Request,
    email_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    eid = parse_uuid(email_id, "email ID")

    try:
        await unlink_email(db, current_user.id, eid)
    except EmailNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked email not found")
