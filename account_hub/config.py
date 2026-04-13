import os

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Minimum password length enforced at registration
MIN_PASSWORD_LENGTH = 8

# Account lockout settings
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/accounthub"

    # Security
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    @model_validator(mode="after")
    def _fix_database_url(self) -> "Settings":
        """Ensure the database URL uses the asyncpg driver."""
        url = self.database_url.strip()
        # Handle postgres:// (used by some providers like Railway/Heroku)
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        self.database_url = url
        return self

    @model_validator(mode="after")
    def _validate_secret_key(self) -> "Settings":
        """Refuse to start with the default secret key in non-test environments."""
        if self.secret_key == "change-me" and os.environ.get("TESTING") != "1":
            raise ValueError(
                "SECRET_KEY is set to the insecure default 'change-me'. "
                "Set a strong random value (>= 32 bytes) in your .env file."
            )
        return self

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
    app_url: str = ""


settings = Settings()
