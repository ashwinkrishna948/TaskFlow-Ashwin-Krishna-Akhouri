import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

_engine = None


def _build_url() -> str:
    return (
        f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:"
        f"{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST', 'pgbouncer')}:"
        f"{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB')}"
    )


def get_engine():
    global _engine
    if _engine is not None:
        return _engine

    _engine = create_async_engine(
        _build_url(),
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
    )

    return _engine


async def dispose_engine():
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def get_db():
    timeout_ms = os.getenv("DB_STATEMENT_TIMEOUT_MS", "5000")
    async with get_engine().begin() as conn:
        await conn.execute(text(f"SET LOCAL statement_timeout = '{timeout_ms}ms'"))
        yield conn
