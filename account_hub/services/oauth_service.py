from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.db.models import LinkedEmail, OAuthState
from account_hub.oauth.providers import FlowType, OAuthProviderConfig, get_provider
from account_hub.security.encryption import encrypt_token


class OAuthServiceError(Exception):
    pass


class InvalidStateError(OAuthServiceError):
    pass


class TokenExchangeFailedError(OAuthServiceError):
    pass


class UserInfoFailedError(OAuthServiceError):
    pass


class EmailAlreadyLinkedError(OAuthServiceError):
    pass


class DeviceCodePendingError(OAuthServiceError):
    """Raised when the device code flow is still waiting for user action."""
    pass


@dataclass
class InitiateResult:
    """Returned by initiate_oauth — either an auth_url or device code info."""
    auth_url: str | None = None
    state: str | None = None
    # Device code flow fields
    user_code: str | None = None
    verification_uri: str | None = None
    device_code: str | None = None
    interval: int | None = None


@dataclass
class LinkResult:
    linked_email_id: uuid.UUID
    email_address: str
    provider: str


async def initiate_oauth(
    db: AsyncSession,
    user_id: uuid.UUID,
    provider_name: str,
    redirect_port: int | None = None,
) -> InitiateResult:
    """Start an OAuth flow. Returns auth URL (loopback) or device code info."""
    provider = get_provider(provider_name)

    # For Apple, encode the local port in state so the relay worker knows where to redirect
    if provider_name == "apple" and redirect_port:
        state = f"{secrets.token_hex(32)}:{redirect_port}"
    else:
        state = secrets.token_hex(32)

    oauth_state = OAuthState(
        state=state,
        user_id=user_id,
        provider=provider_name,
        redirect_port=redirect_port,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),  # noqa: UP017
    )
    db.add(oauth_state)
    await db.commit()

    if provider.flow_type == FlowType.LOOPBACK:
        # Apple uses dlopro.com relay; others use localhost directly
        if provider_name == "apple":
            redirect_uri = "https://dlopro.com/callback"
        else:
            redirect_uri = f"http://127.0.0.1:{redirect_port}/callback"
        params = {
            "client_id": provider.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(provider.scopes),
            "state": state,
            **provider.extra_authorize_params,
        }
        auth_url = f"{provider.authorize_url}?{urlencode(params)}"
        return InitiateResult(auth_url=auth_url, state=state)

    elif provider.flow_type == FlowType.DEVICE_CODE:
        return await _start_device_code_flow(provider, state)

    raise OAuthServiceError(f"Unsupported flow type: {provider.flow_type}")


async def _start_device_code_flow(
    provider: OAuthProviderConfig, state: str
) -> InitiateResult:
    """Request a device code from the provider (Microsoft)."""
    if not provider.device_code_url:
        raise OAuthServiceError(f"No device_code_url configured for {provider.name}")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            provider.device_code_url,
            data={
                "client_id": provider.client_id,
                "scope": " ".join(provider.scopes),
            },
        )

    if resp.status_code != 200:
        raise TokenExchangeFailedError(
            f"Device code request failed: {resp.status_code} {resp.text}"
        )

    data = resp.json()
    return InitiateResult(
        state=state,
        user_code=data.get("user_code"),
        verification_uri=data.get("verification_uri"),
        device_code=data.get("device_code"),
        interval=data.get("interval", 5),
    )


async def handle_oauth_callback(
    db: AsyncSession,
    user_id: uuid.UUID,
    provider_name: str,
    code: str,
    state: str,
) -> LinkResult:
    """Exchange an auth code for tokens and create a linked email."""
    # Validate state
    result = await db.execute(
        select(OAuthState).where(
            OAuthState.state == state,
            OAuthState.provider == provider_name,
            OAuthState.user_id == user_id,
            OAuthState.expires_at > datetime.now(timezone.utc),  # noqa: UP017
        )
    )
    oauth_state = result.scalar_one_or_none()
    if oauth_state is None:
        raise InvalidStateError("Invalid or expired OAuth state")

    redirect_port = oauth_state.redirect_port

    # Delete the state (single-use)
    await db.execute(delete(OAuthState).where(OAuthState.id == oauth_state.id))

    provider = get_provider(provider_name)

    # Exchange code for tokens
    token_data = await _exchange_code(provider, code, redirect_port, provider_name)

    # Get user info (email address)
    access_token = token_data["access_token"]
    user_info = await _get_user_info(provider, access_token)

    email_address = user_info.get("email")
    if not email_address:
        raise UserInfoFailedError("Provider did not return an email address")

    provider_user_id = user_info.get("sub") or user_info.get("id")

    # Check if already linked
    existing = await db.execute(
        select(LinkedEmail).where(
            LinkedEmail.user_id == user_id,
            LinkedEmail.email_address == email_address,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise EmailAlreadyLinkedError(f"{email_address} is already linked to your account")

    # Encrypt and store tokens
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")
    token_expires_at = None
    if expires_in:
        token_expires_at = datetime.now(timezone.utc) + timedelta(  # noqa: UP017
            seconds=int(expires_in)
        )

    linked_email = LinkedEmail(
        user_id=user_id,
        email_address=email_address,
        provider=provider_name,
        provider_user_id=str(provider_user_id) if provider_user_id else None,
        access_token_enc=encrypt_token(access_token),
        refresh_token_enc=encrypt_token(refresh_token) if refresh_token else None,
        token_expires_at=token_expires_at,
        scopes=" ".join(provider.scopes),
        is_verified=True,
    )
    db.add(linked_email)
    await db.commit()
    await db.refresh(linked_email)

    return LinkResult(
        linked_email_id=linked_email.id,
        email_address=email_address,
        provider=provider_name,
    )


async def poll_device_code(
    db: AsyncSession,
    user_id: uuid.UUID,
    provider_name: str,
    device_code: str,
) -> LinkResult:
    """Poll the device code flow for completion. Raises DeviceCodePending if not yet authorized."""
    provider = get_provider(provider_name)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            provider.token_url,
            data={
                "client_id": provider.client_id,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
        )

    if resp.status_code != 200:
        data = resp.json()
        error = data.get("error", "")
        if error == "authorization_pending":
            raise DeviceCodePendingError("User has not yet authorized")
        if error == "slow_down":
            raise DeviceCodePendingError("Slow down — increase polling interval")
        raise TokenExchangeFailedError(f"Device code poll failed: {resp.status_code} {resp.text}")

    token_data = resp.json()
    access_token = token_data["access_token"]

    # Get user info
    user_info = await _get_user_info(provider, access_token)
    email_address = (
        user_info.get("mail")
        or user_info.get("userPrincipalName")
        or user_info.get("email")
    )
    if not email_address:
        raise UserInfoFailedError("Provider did not return an email address")

    provider_user_id = user_info.get("id")

    # Check if already linked
    existing = await db.execute(
        select(LinkedEmail).where(
            LinkedEmail.user_id == user_id,
            LinkedEmail.email_address == email_address,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise EmailAlreadyLinkedError(f"{email_address} is already linked to your account")

    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")
    token_expires_at = None
    if expires_in:
        token_expires_at = datetime.now(timezone.utc) + timedelta(  # noqa: UP017
            seconds=int(expires_in)
        )

    linked_email = LinkedEmail(
        user_id=user_id,
        email_address=email_address,
        provider=provider_name,
        provider_user_id=str(provider_user_id) if provider_user_id else None,
        access_token_enc=encrypt_token(access_token),
        refresh_token_enc=encrypt_token(refresh_token) if refresh_token else None,
        token_expires_at=token_expires_at,
        scopes=" ".join(provider.scopes),
        is_verified=True,
    )
    db.add(linked_email)
    await db.commit()
    await db.refresh(linked_email)

    # Clean up any remaining oauth_states for this user+provider
    await db.execute(
        delete(OAuthState).where(
            OAuthState.user_id == user_id,
            OAuthState.provider == provider_name,
        )
    )
    await db.commit()

    return LinkResult(
        linked_email_id=linked_email.id,
        email_address=email_address,
        provider=provider_name,
    )


async def _exchange_code(
    provider: OAuthProviderConfig, code: str, redirect_port: int | None,
    provider_name: str = "",
) -> dict:
    """Exchange an authorization code for tokens."""
    if provider_name == "apple":
        redirect_uri = "https://dlopro.com/callback"
    elif redirect_port:
        redirect_uri = f"http://127.0.0.1:{redirect_port}/callback"
    else:
        redirect_uri = ""

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            provider.token_url,
            data={
                "client_id": provider.client_id,
                "client_secret": provider.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                **provider.extra_token_params,
            },
        )

    if resp.status_code != 200:
        raise TokenExchangeFailedError(f"Token exchange failed: {resp.status_code} {resp.text}")

    return resp.json()


async def _get_user_info(provider: OAuthProviderConfig, access_token: str) -> dict:
    """Fetch user profile from the provider's userinfo endpoint."""
    if not provider.userinfo_url:
        return {}

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            provider.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if resp.status_code != 200:
        raise UserInfoFailedError(f"Userinfo request failed: {resp.status_code} {resp.text}")

    return resp.json()
