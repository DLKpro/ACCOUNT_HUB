from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.api.dependencies import get_current_user, get_db
from account_hub.db.models import User
from account_hub.services.email_service import (
    EmailNotFound,
    LinkedEmailInfo,
    list_linked_emails,
    unlink_email,
)

router = APIRouter(prefix="/emails", tags=["emails"])


class LinkedEmailResponse(BaseModel):
    id: str
    email_address: str
    provider: str
    is_verified: bool
    linked_at: str


@router.get("", response_model=List[LinkedEmailResponse])
async def list_emails(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    emails = await list_linked_emails(db, current_user.id)
    return [
        LinkedEmailResponse(
            id=str(e.id),
            email_address=e.email_address,
            provider=e.provider,
            is_verified=e.is_verified,
            linked_at=e.linked_at,
        )
        for e in emails
    ]


@router.delete("/{email_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_email(
    email_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid

    try:
        eid = uuid.UUID(email_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email ID")

    try:
        await unlink_email(db, current_user.id, eid)
    except EmailNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked email not found")
