from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from jose import jwt as jose_jwt
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from account_hub.db.models import LinkedEmail, OAuthState
from account_hub.oauth.providers import FlowType, OAuthProviderConfig, get_provider
from account_hub.security.encryption import encrypt_token

security_logger = logging.getLogger("account_hub.security")
logger = logging.getLogger("account_hub.oauth")


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

    # Generate PKCE code verifier for auth code flows
    code_verifier = None
    nonce = None
    if provider.flow_type == FlowType.LOOPBACK:
        code_verifier = secrets.token_urlsafe(64)
        if "openid" in provider.scopes:
            nonce = secrets.token_urlsafe(32)

    oauth_state = OAuthState(
        state=state,
        user_id=user_id,
        provider=provider_name,
        redirect_port=redirect_port,
        code_verifier=code_verifier,
        nonce=nonce,
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

        # PKCE S256 challenge
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")

        params = {
            "client_id": provider.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(provider.scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            **provider.extra_authorize_params,
        }
        if nonce:
            params["nonce"] = nonce
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
        logger.error("Device code request failed: %d %s", resp.status_code, resp.text)
        raise TokenExchangeFailedError("Device code request failed")

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
    code_verifier = oauth_state.code_verifier
    stored_nonce = oauth_state.nonce

    # Delete the state (single-use)
    await db.execute(delete(OAuthState).where(OAuthState.id == oauth_state.id))

    provider = get_provider(provider_name)

    # Exchange code for tokens
    token_data = await _exchange_code(provider, code, redirect_port, provider_name, code_verifier=code_verifier)

    # Validate OIDC nonce if present
    if stored_nonce and "id_token" in token_data:
        id_claims = jose_jwt.get_unverified_claims(token_data["id_token"])
        if id_claims.get("nonce") != stored_nonce:
            raise InvalidStateError("Nonce mismatch in ID token")

    # Get user info (email address)
    access_token = token_data["access_token"]
    if provider_name == "apple":
        # Apple has no userinfo endpoint; user info is in the id_token JWT
        id_token_raw = token_data.get("id_token")
        if not id_token_raw:
            raise UserInfoFailedError("Apple did not return an id_token")
        claims = jose_jwt.get_unverified_claims(id_token_raw)
        user_info = {"email": claims.get("email"), "sub": claims.get("sub")}
    else:
        user_info = await _get_user_info(provider, access_token)

    email_address = user_info.get("email")
    if not email_address:
        raise UserInfoFailedError("Provider did not return an email address")

    provider_user_id = user_info.get("sub") or user_info.get("id")

    linked_email = await _create_linked_email(
        db, user_id, email_address, provider_name, provider_user_id,
        token_data, provider.scopes,
    )

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
        logger.error("Device code poll failed: %d %s", resp.status_code, resp.text)
        raise TokenExchangeFailedError("Device code poll failed")

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

    linked_email = await _create_linked_email(
        db, user_id, email_address, provider_name, provider_user_id,
        token_data, provider.scopes,
    )

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


async def _create_linked_email(
    db: AsyncSession,
    user_id: uuid.UUID,
    email_address: str,
    provider_name: str,
    provider_user_id: str | None,
    token_data: dict,
    scopes: list[str],
) -> LinkedEmail:
    """Check for duplicates, encrypt tokens, persist and return a LinkedEmail."""
    existing = await db.execute(
        select(LinkedEmail).where(
            LinkedEmail.user_id == user_id,
            LinkedEmail.email_address == email_address,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise EmailAlreadyLinkedError(f"{email_address} is already linked to your account")

    access_token = token_data["access_token"]
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
        scopes=" ".join(scopes),
        is_verified=True,
    )
    db.add(linked_email)
    await db.commit()
    await db.refresh(linked_email)

    security_logger.info(
        "SECURITY_EVENT: email_linked user=%s provider=%s email=%s",
        user_id, provider_name, email_address,
    )

    return linked_email


async def _exchange_code(
    provider: OAuthProviderConfig, code: str, redirect_port: int | None,
    provider_name: str = "", *, code_verifier: str | None = None,
) -> dict:
    """Exchange an authorization code for tokens."""
    if provider_name == "apple":
        redirect_uri = "https://dlopro.com/callback"
    elif redirect_port:
        redirect_uri = f"http://127.0.0.1:{redirect_port}/callback"
    else:
        redirect_uri = ""

    if provider_name == "apple":
        from account_hub.config import settings
        from account_hub.oauth.apple_jwt import generate_apple_client_secret
        client_secret = generate_apple_client_secret(
            settings.apple_team_id, settings.apple_client_id,
            settings.apple_key_id, settings.apple_private_key_path,
            private_key=settings.apple_private_key,
        )
    else:
        client_secret = provider.client_secret

    data = {
        "client_id": provider.client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        **provider.extra_token_params,
    }
    if code_verifier:
        data["code_verifier"] = code_verifier

    async with httpx.AsyncClient() as client:
        resp = await client.post(provider.token_url, data=data)

    if resp.status_code != 200:
        logger.error("Token exchange failed: %d %s", resp.status_code, resp.text)
        raise TokenExchangeFailedError("Token exchange failed")

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
        logger.error("Userinfo request failed: %d %s", resp.status_code, resp.text)
        raise UserInfoFailedError("Failed to retrieve user information from provider")

    return resp.json()
