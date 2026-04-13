import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from account_hub.config import settings

ALGORITHM = "HS256"


def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(  # noqa: UP017
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),  # noqa: UP017
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(  # noqa: UP017
        days=settings.refresh_token_expire_days
    )
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),  # noqa: UP017
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> uuid.UUID:
    """Decode and validate a JWT token. Returns the user UUID.

    Raises JWTError if token is invalid, expired, or wrong type.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        raise

    token_type = payload.get("type")
    if token_type != expected_type:
        raise JWTError(f"Expected token type '{expected_type}', got '{token_type}'")

    sub = payload.get("sub")
    if sub is None:
        raise JWTError("Token missing 'sub' claim")

    return uuid.UUID(sub)
