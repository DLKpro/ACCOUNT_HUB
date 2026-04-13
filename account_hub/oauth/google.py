from account_hub.config import settings
from account_hub.oauth.providers import FlowType, OAuthProviderConfig, register_provider


def setup_google() -> None:
    register_provider(OAuthProviderConfig(
        name="google",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        scopes=["openid", "email", "profile"],
        flow_type=FlowType.LOOPBACK,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        extra_authorize_params={
            "access_type": "offline",
            "prompt": "consent",
        },
        revoke_url="https://oauth2.googleapis.com/revoke",
    ))
