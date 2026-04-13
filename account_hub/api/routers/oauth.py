from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.api.dependencies import get_current_user, get_db
from account_hub.api.limiter import limiter
from account_hub.db.models import LinkedEmail, User
from account_hub.services.oauth_service import (
    DeviceCodePendingError,
    EmailAlreadyLinkedError,
    InvalidStateError,
    OAuthServiceError,
    TokenExchangeFailedError,
    UserInfoFailedError,
    handle_oauth_callback,
    initiate_oauth,
    poll_device_code,
)

router = APIRouter(prefix="/oauth", tags=["oauth"])


# --- Request / Response schemas ---


class InitiateRequest(BaseModel):
    provider: str
    redirect_port: int | None = None


class InitiateResponse(BaseModel):
    auth_url: str | None = None
    state: str | None = None
    user_code: str | None = None
    verification_uri: str | None = None
    device_code: str | None = None
    interval: int | None = None


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
@limiter.limit("10/minute")
async def callback(
    request: Request,
    body: CallbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await handle_oauth_callback(
            db, current_user.id, body.provider, body.code, body.state
        )
    except InvalidStateError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )
    except EmailAlreadyLinkedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except (TokenExchangeFailedError, UserInfoFailedError) as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return LinkResponse(
        linked_email_id=str(result.linked_email_id),
        email_address=result.email_address,
        provider=result.provider,
    )


@router.post("/poll")
@limiter.limit("20/minute")
async def poll(
    request: Request,
    body: PollRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await poll_device_code(
            db, current_user.id, body.provider, body.device_code
        )
    except DeviceCodePendingError:
        return PollPendingResponse(status="pending")
    except EmailAlreadyLinkedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except (TokenExchangeFailedError, UserInfoFailedError) as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    return LinkResponse(
        linked_email_id=str(result.linked_email_id),
        email_address=result.email_address,
        provider=result.provider,
    )


# --- Meta Data Deletion Callback ---

logger = logging.getLogger("account_hub.oauth")


def _parse_meta_signed_request(signed_request: str, app_secret: str) -> dict:
    """Decode and verify a Meta signed_request using HMAC-SHA256."""
    parts = signed_request.split(".", 1)
    if len(parts) != 2:
        raise ValueError("Invalid signed_request format")

    encoded_sig, payload = parts
    # Meta uses URL-safe base64 without padding
    sig = base64.urlsafe_b64decode(encoded_sig + "==")
    data = json.loads(base64.urlsafe_b64decode(payload + "=="))

    expected_sig = hmac.new(
        app_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).digest()

    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("Invalid signature")

    return data


class MetaDeletionResponse(BaseModel):
    url: str
    confirmation_code: str


@router.post("/meta/data-deletion", response_model=MetaDeletionResponse)
async def meta_data_deletion(
    request: Request,
    signed_request: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Meta data deletion callback. Called by Meta when a user requests deletion of their data."""
    from account_hub.config import settings
    from account_hub.services.email_service import try_revoke_token

    if not settings.meta_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Not configured",
        )

    try:
        data = _parse_meta_signed_request(signed_request, settings.meta_client_secret)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signed request",
        )

    meta_user_id = str(data.get("user_id", ""))
    if not meta_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing user_id")

    # Find and delete all Meta-linked emails for this provider user
    result = await db.execute(
        select(LinkedEmail).where(
            LinkedEmail.provider == "meta",
            LinkedEmail.provider_user_id == meta_user_id,
        )
    )
    linked_emails = result.scalars().all()

    for linked_email in linked_emails:
        await try_revoke_token(linked_email)

    if linked_emails:
        await db.execute(
            delete(LinkedEmail).where(
                LinkedEmail.provider == "meta",
                LinkedEmail.provider_user_id == meta_user_id,
            )
        )
        await db.commit()

    confirmation_code = uuid.uuid4().hex
    logger.info(
        "META_DATA_DELETION: meta_user_id=%s emails_deleted=%d confirmation=%s",
        meta_user_id, len(linked_emails), confirmation_code,
    )

    app_url = settings.app_url or "https://dlopro.com"
    return MetaDeletionResponse(
        url=f"{app_url}/data-deletion?code={confirmation_code}",
        confirmation_code=confirmation_code,
    )
