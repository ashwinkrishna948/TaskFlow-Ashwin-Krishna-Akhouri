"""
Integration test configuration.

Requires the full stack to be running (docker compose up).
Set BASE_URL env var to override the default http://localhost.
Set DATABASE_URL env var to enable DB-layer verification.
"""
import os
import pytest
import httpx

BASE_URL = os.getenv("BASE_URL", "http://localhost")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://taskflow:taskflow_secret@localhost:5432/taskflow",
)


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def db_conn():
    """Optional psycopg2 connection for DB-layer verification. Skipped if unavailable."""
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        yield conn
        conn.close()
    except Exception:
        yield None


@pytest.fixture(scope="session")
def auth_token(base_url):
    """Register a fresh user and return their JWT token."""
    import uuid
    email = f"integration_{uuid.uuid4().hex[:8]}@test.example"
    with httpx.Client(base_url=base_url) as client:
        r = client.post("/auth/register", json={
            "name": "Integration Tester",
            "email": email,
            "password": "IntTest123!",
        })
        assert r.status_code == 201, f"Register failed: {r.text}"
        r2 = client.post("/auth/login", json={"email": email, "password": "IntTest123!"})
        assert r2.status_code == 200, f"Login failed: {r2.text}"
        return r2.json()["access_token"]


@pytest.fixture(scope="session")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}
