"""Unit tests for app.keyvault — cache, env fallback, missing secret."""
import os
import pytest
from unittest.mock import AsyncMock, patch


# ---------------------------------------------------------------------------
# cached_secret
# ---------------------------------------------------------------------------

def test_cached_secret_returns_from_cache():
    import app.keyvault as kv
    kv._secrets["my-secret"] = "cached-value"
    assert kv.cached_secret("my-secret") == "cached-value"
    del kv._secrets["my-secret"]


def test_cached_secret_env_fallback(monkeypatch):
    import app.keyvault as kv
    kv._secrets.pop("fallback-secret", None)
    monkeypatch.setenv("FALLBACK_ENV", "env-value")
    assert kv.cached_secret("fallback-secret", env_fallback="FALLBACK_ENV") == "env-value"


def test_cached_secret_raises_when_missing(monkeypatch):
    import app.keyvault as kv
    kv._secrets.pop("missing-secret", None)
    monkeypatch.delenv("MISSING_ENV", raising=False)
    with pytest.raises(RuntimeError, match="not found"):
        kv.cached_secret("missing-secret", env_fallback="MISSING_ENV")


# ---------------------------------------------------------------------------
# load_secrets — no vault configured
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_load_secrets_uses_env_when_no_vault(monkeypatch):
    import app.keyvault as kv
    monkeypatch.setattr(kv, "_VAULT_URL", None)
    monkeypatch.setenv("JWT_SECRET", "env-jwt-secret")
    kv._secrets.clear()

    result = await kv.load_secrets()

    assert result.get("jwt-secret") == "env-jwt-secret"
    assert kv._secrets.get("jwt-secret") == "env-jwt-secret"


@pytest.mark.asyncio
async def test_load_secrets_vault_secret_takes_priority(monkeypatch):
    import app.keyvault as kv
    monkeypatch.setattr(kv, "_VAULT_URL", "http://fakevault")
    monkeypatch.setenv("JWT_SECRET", "env-secret")
    kv._secrets.clear()

    with patch("app.keyvault.get_secret", new=AsyncMock(return_value="vault-secret")):
        result = await kv.load_secrets()

    assert result.get("jwt-secret") == "vault-secret"


@pytest.mark.asyncio
async def test_load_secrets_missing_logs_warning(monkeypatch, caplog):
    import app.keyvault as kv
    monkeypatch.setattr(kv, "_VAULT_URL", None)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    kv._secrets.clear()

    result = await kv.load_secrets()

    assert "jwt-secret" not in result
