from __future__ import annotations

import time
from pathlib import Path

from jose import jwt


def generate_apple_client_secret(
    team_id: str,
    client_id: str,
    key_id: str,
    private_key_path: str,
    private_key: str = "",
) -> str:
    """Generate an ES256-signed JWT used as Apple's OAuth client_secret.

    Apple requires this instead of a static client secret. Max lifetime is 6 months.

    Accepts either:
      - private_key: PEM string directly (preferred for Railway / containers)
      - private_key_path: path to .p8 file (local development)
    """
    if private_key:
        key_data = private_key
    else:
        key_data = Path(private_key_path).read_text()

    now = int(time.time())
    claims = {
        "iss": team_id,
        "iat": now,
        "exp": now + (86400 * 180),  # 180 days
        "aud": "https://appleid.apple.com",
        "sub": client_id,
    }
    return jwt.encode(claims, key_data, algorithm="ES256", headers={"kid": key_id})
