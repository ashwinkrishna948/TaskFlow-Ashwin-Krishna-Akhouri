import os

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from slowapi.util import get_remote_address

from app import keyvault

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
_bearer = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def _get_secret() -> str:
    return keyvault.cached_secret("jwt-secret", env_fallback="JWT_SECRET")


def create_token(user_id: str, email: str) -> str:
    from datetime import datetime, timedelta, timezone

    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, _get_secret(), algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, _get_secret(), algorithms=["HS256"])


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="missing token")
    try:
        return decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid token")


def get_user_or_ip(request: Request) -> str:
    """SlowAPI key function — user_id when authenticated, IP otherwise."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = decode_token(auth[7:])
            return f"user:{payload['user_id']}"
        except Exception:
            pass
    return f"ip:{get_remote_address(request)}"
