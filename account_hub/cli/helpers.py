from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
from jose import JWTError

from account_hub.config import settings
from account_hub.security.jwt import decode_token

CREDENTIALS_DIR = Path.home() / ".accounthub"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"


def _ensure_credentials_dir() -> None:
    """Create ~/.accounthub/ with 0700 permissions if it doesn't exist."""
    if not CREDENTIALS_DIR.exists():
        CREDENTIALS_DIR.mkdir(mode=0o700, parents=True)
    else:
        current = CREDENTIALS_DIR.stat().st_mode & 0o777
        if current != 0o700:
            os.chmod(CREDENTIALS_DIR, 0o700)


def save_credentials(access_token: str, refresh_token: str, api_url: Optional[str] = None) -> None:
    """Save tokens to ~/.accounthub/credentials.json with secure permissions."""
    _ensure_credentials_dir()

    data = {
        "api_url": api_url or f"http://{settings.api_host}:{settings.api_port}",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }

    # Write with 0600 permissions
    fd = os.open(str(CREDENTIALS_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        os.close(fd)
        raise


def load_credentials() -> Optional[dict]:
    """Load credentials from ~/.accounthub/credentials.json. Returns None if missing."""
    if not CREDENTIALS_FILE.exists():
        return None

    # Warn if permissions are too open
    current = CREDENTIALS_FILE.stat().st_mode & 0o777
    if current != 0o600:
        from rich.console import Console

        Console(stderr=True).print(
            f"[yellow]Warning: {CREDENTIALS_FILE} has permissions {oct(current)}, "
            f"should be 0600. Run: chmod 600 {CREDENTIALS_FILE}[/yellow]"
        )

    with open(CREDENTIALS_FILE) as f:
        return json.load(f)


def clear_credentials() -> None:
    """Delete the credentials file."""
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()


def get_api_url() -> str:
    """Get the API URL from saved credentials or config defaults."""
    creds = load_credentials()
    if creds and "api_url" in creds:
        return creds["api_url"]
    return f"http://{settings.api_host}:{settings.api_port}"


def get_auth_headers() -> dict:
    """Get Authorization headers from saved credentials. Raises if not logged in."""
    creds = load_credentials()
    if not creds or "access_token" not in creds:
        from rich.console import Console

        Console(stderr=True).print("[red]Not logged in. Run: accounthub auth login[/red]")
        raise SystemExit(1)

    return {"Authorization": f"Bearer {creds['access_token']}"}


def get_client() -> httpx.Client:
    """Return an httpx client configured with the API base URL and auth headers."""
    return httpx.Client(
        base_url=get_api_url(),
        headers=get_auth_headers(),
        timeout=30.0,
    )


def get_anon_client() -> httpx.Client:
    """Return an httpx client without auth headers (for register/login)."""
    return httpx.Client(
        base_url=get_api_url(),
        timeout=30.0,
    )
