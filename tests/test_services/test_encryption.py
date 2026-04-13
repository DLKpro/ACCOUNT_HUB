from account_hub.security.encryption import decrypt_token, encrypt_token


def test_encrypt_decrypt_roundtrip():
    plaintext = "my-oauth-access-token-12345"
    ciphertext = encrypt_token(plaintext)
    assert decrypt_token(ciphertext) == plaintext


def test_ciphertext_is_different_from_plaintext():
    plaintext = "secret-token"
    ciphertext = encrypt_token(plaintext)
    assert ciphertext != plaintext


def test_different_plaintexts_produce_different_ciphertexts():
    c1 = encrypt_token("token-one")
    c2 = encrypt_token("token-two")
    assert c1 != c2


def test_same_plaintext_produces_different_ciphertexts():
    """Fernet uses a random IV, so same input should produce different output."""
    c1 = encrypt_token("same-token")
    c2 = encrypt_token("same-token")
    assert c1 != c2
    assert decrypt_token(c1) == "same-token"
    assert decrypt_token(c2) == "same-token"


def test_empty_string():
    ciphertext = encrypt_token("")
    assert decrypt_token(ciphertext) == ""


def test_long_token():
    long_token = "a" * 2048
    ciphertext = encrypt_token(long_token)
    assert decrypt_token(ciphertext) == long_token
