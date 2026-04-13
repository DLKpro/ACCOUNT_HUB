from __future__ import annotations

import time
from pathlib import Path

from jose import jwt


def generate_apple_client_secret(
    team_id: str,
    client_id: str,
    key_id: str,
    private_key_path: str,
) -> str:
    """Generate an ES256-signed JWT used as Apple's OAuth client_secret.

    Apple requires this instead of a static client secret. Max lifetime is 6 months.
    """
    private_key = Path(private_key_path).read_text()
    now = int(time.time())
    claims = {
        "iss": team_id,
        "iat": now,
        "exp": now + (86400 * 180),  # 180 days
        "aud": "https://appleid.apple.com",
        "sub": client_id,
    }
    return jwt.encode(claims, private_key, algorithm="ES256", headers={"kid": key_id})
