import os
from typing import Optional

import httpx
import structlog

log = structlog.get_logger()

_VAULT_URL: Optional[str] = os.getenv("AZURE_KEYVAULT_URL")
_secrets: dict[str, str] = {}


async def get_secret(name: str) -> Optional[str]:
    """Fetch one secret from Key Vault. Returns None if not configured or missing."""
    if not _VAULT_URL:
        return None

    url = f"{_VAULT_URL}/secrets/{name}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()["value"]
    except Exception as exc:
        log.warning("keyvault_get_failed", secret=name, error=str(exc))
        return None


async def load_secrets() -> dict[str, str]:
    """Load secrets from Key Vault into the module cache at startup."""
    if _VAULT_URL:
        log.info("keyvault_loading", vault_url=_VAULT_URL)
    else:
        log.info(
            "keyvault_skipped",
            msg="AZURE_KEYVAULT_URL not set — using env vars for all secrets",
        )

    mapping = {
        "jwt-secret": "JWT_SECRET",
    }

    loaded: dict[str, str] = {}
    for secret_name, env_fallback in mapping.items():
        value = await get_secret(secret_name)
        if value:
            log.info("keyvault_secret_loaded", secret=secret_name, source="vault")
        else:
            value = os.getenv(env_fallback, "")
            if value:
                log.info(
                    "keyvault_secret_loaded",
                    secret=secret_name,
                    source=f"env:{env_fallback}",
                )
            else:
                log.warning("keyvault_secret_missing", secret=secret_name)

        if value:
            loaded[secret_name] = value
            _secrets[secret_name] = value

    return loaded


def cached_secret(name: str, env_fallback: Optional[str] = None) -> str:
    """Return a secret from cache. Falls back to env var. Raises if neither is set."""
    if name in _secrets:
        return _secrets[name]
    if env_fallback:
        val = os.getenv(env_fallback, "")
        if val:
            return val
    raise RuntimeError(
        f"Secret '{name}' not found in Key Vault cache or env var '{env_fallback}'. "
        "Ensure AZURE_KEYVAULT_URL is set and the vault was seeded."
    )
