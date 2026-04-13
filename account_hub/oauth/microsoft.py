from account_hub.config import settings
from account_hub.oauth.providers import FlowType, OAuthProviderConfig, register_provider


def setup_microsoft() -> None:
    tenant = settings.microsoft_tenant_id
    register_provider(OAuthProviderConfig(
        name="microsoft",
        authorize_url=f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
        token_url=f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        userinfo_url="https://graph.microsoft.com/v1.0/me",
        scopes=["User.Read", "openid", "email", "profile", "offline_access"],
        flow_type=FlowType.DEVICE_CODE,
        client_id=settings.microsoft_client_id,
        client_secret=settings.microsoft_client_secret,
        device_code_url=f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/devicecode",
    ))
