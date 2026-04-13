import uuid

import pytest
from jose import JWTError

from account_hub.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
)


def test_create_and_decode_access_token():
    uid = uuid.uuid4()
    token = create_access_token(uid)
    decoded_uid = decode_token(token, expected_type="access")
    assert decoded_uid == uid


def test_create_and_decode_refresh_token():
    uid = uuid.uuid4()
    token = create_refresh_token(uid)
    decoded_uid = decode_token(token, expected_type="refresh")
    assert decoded_uid == uid


def test_access_token_rejected_as_refresh():
    uid = uuid.uuid4()
    token = create_access_token(uid)
    with pytest.raises(JWTError, match="Expected token type 'refresh'"):
        decode_token(token, expected_type="refresh")


def test_refresh_token_rejected_as_access():
    uid = uuid.uuid4()
    token = create_refresh_token(uid)
    with pytest.raises(JWTError, match="Expected token type 'access'"):
        decode_token(token, expected_type="access")


def test_invalid_token_raises():
    with pytest.raises(JWTError):
        decode_token("not-a-valid-token")


def test_different_users_get_different_tokens():
    t1 = create_access_token(uuid.uuid4())
    t2 = create_access_token(uuid.uuid4())
    assert t1 != t2
