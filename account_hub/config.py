from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/accounthub"

    # Security
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    # Microsoft OAuth
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant_id: str = "common"

    # Apple OAuth
    apple_client_id: str = ""
    apple_team_id: str = ""
    apple_key_id: str = ""
    apple_private_key_path: str = ""

    # Meta OAuth
    meta_client_id: str = ""
    meta_client_secret: str = ""

    # HIBP
    hibp_api_key: str = ""

    # API
    api_host: str = "127.0.0.1"
    api_port: int = 8000


settings = Settings()
