from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.api.limiter import limiter

from account_hub.api.dependencies import get_current_user, get_db
from account_hub.db.models import User
from account_hub.services.user_service import (
    InvalidCredentials,
    InvalidToken,
    UsernameInvalid,
    UsernameTaken,
    authenticate_user,
    delete_account,
    refresh_tokens,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Request / Response schemas ---


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class DeleteAccountRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegisterResponse(BaseModel):
    id: str
    username: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    is_active: bool
    created_at: str


# --- Endpoints ---


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        user, tokens = await register_user(db, body.username, body.password)
    except UsernameInvalid as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except UsernameTaken as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return RegisterResponse(
        id=str(user.id),
        username=user.username,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        _user, tokens = await authenticate_user(db, body.username, body.password)
    except InvalidCredentials as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        tokens = await refresh_tokens(db, body.refresh_token)
    except InvalidToken as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
    )


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    body: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await delete_account(db, current_user, body.password)
    except InvalidCredentials as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
