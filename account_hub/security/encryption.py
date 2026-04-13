import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from account_hub.config import settings

_SALT = b"account-hub-token-encryption"


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a Fernet-compatible key from an arbitrary secret string using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=480_000,
    )
    key = kdf.derive(secret.encode())
    return base64.urlsafe_b64encode(key)


_fernet = Fernet(_derive_fernet_key(settings.secret_key))


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string. Returns a base64-encoded ciphertext."""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt an encrypted token string. Returns the original plaintext."""
    return _fernet.decrypt(ciphertext.encode()).decode()
