"""Integration tests for /auth endpoints."""
import uuid
import httpx
import pytest


def test_register_creates_user(base_url):
    email = f"reg_{uuid.uuid4().hex[:8]}@test.example"
    with httpx.Client(base_url=base_url) as client:
        r = client.post("/auth/register", json={
            "name": "Test User",
            "email": email,
            "password": "TestPass123!",
        })
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == email
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body


def test_register_duplicate_email_returns_409(base_url):
    email = f"dup_{uuid.uuid4().hex[:8]}@test.example"
    with httpx.Client(base_url=base_url) as client:
        client.post("/auth/register", json={"name": "A", "email": email, "password": "TestPass123!"})
        r = client.post("/auth/register", json={"name": "B", "email": email, "password": "TestPass123!"})
    assert r.status_code == 409


def test_login_returns_token(base_url):
    email = f"login_{uuid.uuid4().hex[:8]}@test.example"
    with httpx.Client(base_url=base_url) as client:
        client.post("/auth/register", json={"name": "L", "email": email, "password": "TestPass123!"})
        r = client.post("/auth/login", json={"email": email, "password": "TestPass123!"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password_returns_401(base_url):
    email = f"wp_{uuid.uuid4().hex[:8]}@test.example"
    with httpx.Client(base_url=base_url) as client:
        client.post("/auth/register", json={"name": "W", "email": email, "password": "TestPass123!"})
        r = client.post("/auth/login", json={"email": email, "password": "wrongpassword"})
    assert r.status_code == 401


def test_me_returns_current_user(base_url, auth_headers):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.get("/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert "id" in body
    assert "email" in body


def test_me_without_token_returns_401(base_url):
    with httpx.Client(base_url=base_url) as client:
        r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_with_invalid_token_returns_401(base_url):
    with httpx.Client(base_url=base_url, headers={"Authorization": "Bearer invalid.token.here"}) as client:
        r = client.get("/auth/me")
    assert r.status_code == 401


def test_healthz(base_url):
    with httpx.Client(base_url=base_url) as client:
        r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
