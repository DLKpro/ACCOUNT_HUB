from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.api.dependencies import get_current_user, get_db
from account_hub.api.limiter import limiter
from account_hub.db.models import User
from account_hub.services.password_reset_service import (
    InvalidResetTokenError,
    UserNotFoundError,
    complete_password_reset,
    request_password_reset,
)
from account_hub.services.password_reset_service import (
    PasswordTooShortError as ResetPasswordTooShortError,
)
from account_hub.services.email_verification_service import (
    AlreadyVerifiedError,
    InvalidVerificationTokenError,
    create_verification_token,
    verify_email,
)
from account_hub.services.user_service import (
    AccountLockedError,
    EmailInvalidError,
    EmailTakenError,
    InvalidCredentialsError,
    InvalidTokenError,
    PasswordTooShortError,
    UsernameInvalidError,
    UsernameTakenError,
    authenticate_user,
    delete_account,
    refresh_tokens,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Request / Response schemas ---


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str  # accepts username or email
    password: str


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    pass  # uses current authenticated user


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    username: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class DeleteAccountRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegisterResponse(BaseModel):
    id: str
    username: str
    email: str
    email_verified: bool
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    verification_url: str | None = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    email_verified: bool
    is_active: bool
    created_at: str


# --- Endpoints ---


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    import logging
    logger = logging.getLogger("account_hub.security")

    try:
        user, tokens = await register_user(db, body.username, body.email, body.password)
    except (UsernameInvalidError, EmailInvalidError, PasswordTooShortError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (UsernameTakenError, EmailTakenError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    # Generate email verification token
    vtoken = await create_verification_token(db, user.id)
    verification_url = f"/verify-email?token={vtoken}"
    logger.info("VERIFICATION_LINK: %s (user=%s)", verification_url, user.username)

    return RegisterResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        email_verified=False,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        verification_url=verification_url,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        _user, tokens = await authenticate_user(db, body.username, body.password)
    except AccountLockedError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh(request: Request, body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        tokens = await refresh_tokens(db, body.refresh_token)
    except InvalidTokenError as e:
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
        email_verified=current_user.email_verified,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
    )


@router.post("/verify-email")
@limiter.limit("10/minute")
async def verify_email_endpoint(
    request: Request, body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)
):
    """Verify email address using the token from the verification link."""
    try:
        user = await verify_email(db, body.token)
    except InvalidVerificationTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except AlreadyVerifiedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return {"message": "Email verified successfully.", "email": user.email}


@router.post("/resend-verification")
@limiter.limit("3/minute")
async def resend_verification(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resend the email verification token."""
    import logging
    logger = logging.getLogger("account_hub.security")

    if current_user.email_verified:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already verified")

    vtoken = await create_verification_token(db, current_user.id)
    verification_url = f"/verify-email?token={vtoken}"
    logger.info("VERIFICATION_LINK: %s (user=%s)", verification_url, current_user.username)

    return {"message": "Verification link generated.", "verification_url": verification_url}


@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(
    request: Request, body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)
):
    """Request a password reset token. The token is logged to the server console."""
    import logging

    logger = logging.getLogger("account_hub.security")
    try:
        token = await request_password_reset(db, body.username)
    except UserNotFoundError:
        # Don't reveal whether the user exists
        return {"message": "If that account exists, a reset link has been generated."}

    reset_url = f"/reset-password?token={token}"
    logger.info(
        "PASSWORD_RESET_LINK: %s (username=%s)", reset_url, body.username
    )
    # In production, you would email this link instead of logging it
    return {
        "message": "If that account exists, a reset link has been generated.",
        "reset_url": reset_url,
    }


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(
    request: Request, body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
):
    """Complete a password reset using a valid token."""
    try:
        await complete_password_reset(db, body.token, body.new_password)
    except InvalidResetTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ResetPasswordTooShortError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"message": "Password reset successfully. You can now log in."}


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/minute")
async def delete_my_account(
    request: Request,
    body: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await delete_account(db, current_user, body.password)
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
