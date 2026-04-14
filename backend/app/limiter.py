
import os

from slowapi import Limiter

from app.auth import get_user_or_ip

_REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

limiter = Limiter(
    key_func=get_user_or_ip,
    default_limits=["200/minute"],
    storage_uri=_REDIS_URL,
)
