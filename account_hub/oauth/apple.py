from account_hub.config import settings
from account_hub.oauth.providers import FlowType, OAuthProviderConfig, register_provider


def setup_apple() -> None:
    register_provider(OAuthProviderConfig(
        name="apple",
        authorize_url="https://appleid.apple.com/auth/authorize",
        token_url="https://appleid.apple.com/auth/token",
        userinfo_url="",  # Apple returns user info in the ID token, not a userinfo endpoint
        scopes=["name", "email"],
        flow_type=FlowType.LOOPBACK,
        client_id=settings.apple_client_id,
        client_secret="",  # Generated dynamically as a JWT — handled in oauth_service
        extra_authorize_params={
            "response_mode": "form_post",
        },
    ))
