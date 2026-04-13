from account_hub.config import settings
from account_hub.oauth.providers import FlowType, OAuthProviderConfig, register_provider


def setup_meta() -> None:
    register_provider(OAuthProviderConfig(
        name="meta",
        authorize_url="https://www.facebook.com/v19.0/dialog/oauth",
        token_url="https://graph.facebook.com/v19.0/oauth/access_token",
        userinfo_url="https://graph.facebook.com/v19.0/me?fields=id,name,email",
        scopes=["email", "public_profile"],
        flow_type=FlowType.LOOPBACK,
        client_id=settings.meta_client_id,
        client_secret=settings.meta_client_secret,
    ))
