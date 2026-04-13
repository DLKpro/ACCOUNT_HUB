from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.api.dependencies import get_current_user, get_db
from account_hub.db.models import User
from account_hub.services.oauth_service import (
    DeviceCodePending,
    EmailAlreadyLinked,
    InvalidState,
    OAuthServiceError,
    TokenExchangeFailed,
    UserInfoFailed,
    handle_oauth_callback,
    initiate_oauth,
    poll_device_code,
)

router = APIRouter(prefix="/oauth", tags=["oauth"])


# --- Request / Response schemas ---


class InitiateRequest(BaseModel):
    provider: str
    redirect_port: Optional[int] = None


class InitiateResponse(BaseModel):
    auth_url: Optional[str] = None
    state: Optional[str] = None
    user_code: Optional[str] = None
    verification_uri: Optional[str] = None
    device_code: Optional[str] = None
    interval: Optional[int] = None


class CallbackRequest(BaseModel):
    provider: str
    code: str
    state: str


class PollRequest(BaseModel):
    provider: str
    device_code: str


class LinkResponse(BaseModel):
    linked_email_id: str
    email_address: str
    provider: str


class PollPendingResponse(BaseModel):
    status: str = "pending"


# --- Endpoints ---


@router.post("/initiate", response_model=InitiateResponse)
async def initiate(
    body: InitiateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await initiate_oauth(
            db, current_user.id, body.provider, body.redirect_port
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except OAuthServiceError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return InitiateResponse(
        auth_url=result.auth_url,
        state=result.state,
        user_code=result.user_code,
        verification_uri=result.verification_uri,
        device_code=result.device_code,
        interval=result.interval,
    )


@router.post("/callback", response_model=LinkResponse)
async def callback(
    body: CallbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await handle_oauth_callback(
            db, current_user.id, body.provider, body.code, body.state
        )
    except InvalidState:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )
    except EmailAlreadyLinked as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except (TokenExchangeFailed, UserInfoFailed) as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return LinkResponse(
        linked_email_id=str(result.linked_email_id),
        email_address=result.email_address,
        provider=result.provider,
    )


@router.post("/poll")
async def poll(
    body: PollRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await poll_device_code(
            db, current_user.id, body.provider, body.device_code
        )
    except DeviceCodePending:
        return PollPendingResponse(status="pending")
    except EmailAlreadyLinked as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except (TokenExchangeFailed, UserInfoFailed) as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return LinkResponse(
        linked_email_id=str(result.linked_email_id),
        email_address=result.email_address,
        provider=result.provider,
    )
