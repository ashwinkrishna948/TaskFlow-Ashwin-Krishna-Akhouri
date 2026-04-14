"""Unit tests for app.auth — password hashing, JWT creation/decoding, dependencies."""
import os
import time
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")


from app.auth import (
    hash_password,
    verify_password,
    create_token,
    decode_token,
    get_current_user,
)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def test_hash_password_returns_bcrypt_hash():
    h = hash_password("mypassword")
    assert h.startswith("$2b$")


def test_hash_password_different_salts():
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2


def test_verify_password_correct():
    h = hash_password("secret123")
    assert verify_password("secret123", h) is True


def test_verify_password_wrong():
    h = hash_password("secret123")
    assert verify_password("wrong", h) is False


# ---------------------------------------------------------------------------
# JWT creation and decoding
# ---------------------------------------------------------------------------

def test_create_token_is_string():
    token = create_token("user-id-1", "user@example.com")
    assert isinstance(token, str)
    assert len(token) > 20


def test_decode_token_roundtrip():
    token = create_token("user-id-1", "user@example.com")
    payload = decode_token(token)
    assert payload["user_id"] == "user-id-1"
    assert payload["email"] == "user@example.com"
    assert "exp" in payload


def test_decode_token_invalid_raises():
    import jwt
    with pytest.raises(jwt.InvalidTokenError):
        decode_token("not.a.valid.token")


def test_decode_token_wrong_secret_raises():
    import jwt
    token = jwt.encode({"user_id": "x"}, "wrong-secret", algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token)


def test_decode_token_expired_raises():
    import jwt
    from datetime import datetime, timedelta, timezone
    payload = {
        "user_id": "x",
        "email": "x@x.com",
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
    }
    token = jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)


# ---------------------------------------------------------------------------
# get_current_user dependency
# ---------------------------------------------------------------------------

def test_get_current_user_no_credentials_raises_401():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(None)
    assert exc_info.value.status_code == 401


def test_get_current_user_valid_token_returns_payload():
    from fastapi.security import HTTPAuthorizationCredentials
    token = create_token("uid-42", "test@example.com")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    payload = get_current_user(creds)
    assert payload["user_id"] == "uid-42"
    assert payload["email"] == "test@example.com"


def test_get_current_user_invalid_token_raises_401():
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad.token.here")
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(creds)
    assert exc_info.value.status_code == 401
