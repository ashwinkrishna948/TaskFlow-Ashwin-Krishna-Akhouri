"""Integration tests for /projects endpoints — CRUD, auth rules, pagination, DB verification."""
import uuid
import httpx
import pytest


@pytest.fixture
def project(base_url, auth_headers):
    """Create a project and return its response body."""
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post("/projects", json={"name": "Test Project", "description": "desc"})
    assert r.status_code == 201
    return r.json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def test_create_project_returns_201(base_url, auth_headers):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post("/projects", json={"name": "My Project"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "My Project"
    assert "id" in body
    assert "owner_id" in body


def test_create_project_description_optional(base_url, auth_headers):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post("/projects", json={"name": "No Desc"})
    assert r.status_code == 201
    assert r.json()["description"] is None


def test_create_project_unauthenticated_returns_401(base_url):
    with httpx.Client(base_url=base_url) as client:
        r = client.post("/projects", json={"name": "No Auth"})
    assert r.status_code == 401


def test_create_project_name_too_long_returns_400(base_url, auth_headers):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post("/projects", json={"name": "x" * 501})
    assert r.status_code in (400, 422)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

def test_list_projects_returns_200(base_url, auth_headers, project):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.get("/projects")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_projects_pagination(base_url, auth_headers):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.get("/projects?page=1&page_size=2")
    assert r.status_code == 200
    assert len(r.json()) <= 2


def test_list_projects_page_size_max(base_url, auth_headers):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.get("/projects?page_size=101")
    assert r.status_code in (400, 422)


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------

def test_get_project_returns_200_with_tasks(base_url, auth_headers, project):
    pid = project["id"]
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.get(f"/projects/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == pid
    assert "tasks" in body
    assert isinstance(body["tasks"], list)


def test_get_project_idor_returns_404(base_url, auth_headers):
    fake_id = str(uuid.uuid4())
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.get(f"/projects/{fake_id}")
    assert r.status_code == 404


def test_get_project_invalid_uuid_returns_422(base_url, auth_headers):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.get("/projects/not-a-uuid")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def test_update_project_name(base_url, auth_headers, project):
    pid = project["id"]
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.patch(f"/projects/{pid}", json={"name": "Updated Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "Updated Name"


def test_update_project_non_owner_returns_404(base_url, project):
    pid = project["id"]
    email = f"other_{uuid.uuid4().hex[:8]}@test.example"
    with httpx.Client(base_url=base_url) as client:
        client.post("/auth/register", json={"name": "Other", "email": email, "password": "TestPass123!"})
        r2 = client.post("/auth/login", json={"email": email, "password": "TestPass123!"})
        token = r2.json()["access_token"]
        r = client.patch(f"/projects/{pid}", json={"name": "Hijack"},
                         headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def test_delete_project_returns_204(base_url, auth_headers):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post("/projects", json={"name": "To Delete"})
        pid = r.json()["id"]
        r2 = client.delete(f"/projects/{pid}")
    assert r2.status_code == 204


def test_delete_project_subsequent_get_returns_404(base_url, auth_headers):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post("/projects", json={"name": "Gone"})
        pid = r.json()["id"]
        client.delete(f"/projects/{pid}")
        r2 = client.get(f"/projects/{pid}")
    assert r2.status_code == 404


# ---------------------------------------------------------------------------
# DB verification
# ---------------------------------------------------------------------------

def test_create_project_exists_in_db(base_url, auth_headers, db_conn):
    if db_conn is None:
        pytest.skip("DATABASE_URL not available")
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post("/projects", json={"name": "DB Check Project"})
    pid = r.json()["id"]
    with db_conn.cursor() as cur:
        cur.execute("SELECT id, name FROM projects WHERE id = %s", (pid,))
        row = cur.fetchone()
    assert row is not None
    assert str(row[0]) == pid


def test_delete_project_removed_from_db(base_url, auth_headers, db_conn):
    if db_conn is None:
        pytest.skip("DATABASE_URL not available")
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post("/projects", json={"name": "Hard Delete Check"})
        pid = r.json()["id"]
        client.delete(f"/projects/{pid}")
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM projects WHERE id = %s", (pid,))
        row = cur.fetchone()
    assert row is None
