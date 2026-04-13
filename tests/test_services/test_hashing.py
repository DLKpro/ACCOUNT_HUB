from account_hub.security.hashing import hash_password, verify_password


def test_hash_password_returns_bcrypt_hash():
    h = hash_password("mypassword")
    assert h.startswith("$2b$")
    assert len(h) == 60


def test_verify_correct_password():
    h = hash_password("correct-password")
    assert verify_password("correct-password", h) is True


def test_verify_wrong_password():
    h = hash_password("correct-password")
    assert verify_password("wrong-password", h) is False


def test_different_passwords_produce_different_hashes():
    h1 = hash_password("password1")
    h2 = hash_password("password2")
    assert h1 != h2


def test_same_password_produces_different_hashes():
    """bcrypt uses a random salt, so same input should produce different hashes."""
    h1 = hash_password("same-password")
    h2 = hash_password("same-password")
    assert h1 != h2
    assert verify_password("same-password", h1) is True
    assert verify_password("same-password", h2) is True
