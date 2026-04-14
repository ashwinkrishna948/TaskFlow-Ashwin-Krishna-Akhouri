"""Integration tests for /projects/:id/tasks endpoints — CRUD, filters, idempotency, soft delete, DB verification."""
import uuid
import httpx
import pytest


@pytest.fixture
def project_id(base_url, auth_headers):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post("/projects", json={"name": "Task Test Project"})
    assert r.status_code == 201
    return r.json()["id"]


@pytest.fixture
def task(base_url, auth_headers, project_id):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post(f"/projects/{project_id}/tasks", json={"title": "My Task"})
    assert r.status_code == 201
    return r.json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def test_create_task_returns_201(base_url, auth_headers, project_id):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post(f"/projects/{project_id}/tasks", json={"title": "New Task"})
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "New Task"
    assert body["status"] == "todo"
    assert body["priority"] == "medium"
    assert body["project_id"] == project_id


def test_create_task_with_all_fields(base_url, auth_headers, project_id):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post(f"/projects/{project_id}/tasks", json={
            "title": "Full Task",
            "description": "Some description",
            "status": "in_progress",
            "priority": "high",
            "due_date": "2026-12-31",
        })
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "in_progress"
    assert body["priority"] == "high"
    assert body["due_date"] == "2026-12-31"


def test_create_task_missing_title_returns_400(base_url, auth_headers, project_id):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post(f"/projects/{project_id}/tasks", json={"description": "no title"})
    assert r.status_code in (400, 422)


def test_create_task_unauthenticated_returns_401(base_url, project_id):
    with httpx.Client(base_url=base_url) as client:
        r = client.post(f"/projects/{project_id}/tasks", json={"title": "t"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_idempotency_key_returns_same_task(base_url, auth_headers, project_id):
    key = f"idem-{uuid.uuid4().hex}"
    headers = {**auth_headers, "Idempotency-Key": key}
    with httpx.Client(base_url=base_url, headers=headers) as client:
        r1 = client.post(f"/projects/{project_id}/tasks", json={"title": "Idempotent Task"})
        r2 = client.post(f"/projects/{project_id}/tasks", json={"title": "Idempotent Task"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

def test_list_tasks_returns_200(base_url, auth_headers, project_id, task):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.get(f"/projects/{project_id}/tasks")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_tasks_filter_by_status(base_url, auth_headers, project_id):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        client.post(f"/projects/{project_id}/tasks", json={"title": "Todo task", "status": "todo"})
        client.post(f"/projects/{project_id}/tasks", json={"title": "In progress", "status": "in_progress"})
        r = client.get(f"/projects/{project_id}/tasks?status=todo")
    assert r.status_code == 200
    tasks = r.json()
    assert all(t["status"] == "todo" for t in tasks)


def test_list_tasks_pagination(base_url, auth_headers, project_id):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.get(f"/projects/{project_id}/tasks?page=1&page_size=1")
    assert r.status_code == 200
    assert len(r.json()) <= 1


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------

def test_get_task_returns_200(base_url, auth_headers, project_id, task):
    tid = task["id"]
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.get(f"/projects/{project_id}/tasks/{tid}")
    assert r.status_code == 200
    assert r.json()["id"] == tid


def test_get_task_not_found_returns_404(base_url, auth_headers, project_id):
    fake_id = str(uuid.uuid4())
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.get(f"/projects/{project_id}/tasks/{fake_id}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def test_update_task_status(base_url, auth_headers, project_id, task):
    tid = task["id"]
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.patch(f"/projects/{project_id}/tasks/{tid}", json={"status": "in_progress"})
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"


def test_update_task_invalid_status_transition_returns_422(base_url, auth_headers, project_id):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post(f"/projects/{project_id}/tasks", json={"title": "t", "status": "todo"})
        tid = r.json()["id"]
        r2 = client.patch(f"/projects/{project_id}/tasks/{tid}", json={"status": "invalid_status"})
    assert r2.status_code in (400, 422)


def test_update_task_partial_update(base_url, auth_headers, project_id, task):
    tid = task["id"]
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.patch(f"/projects/{project_id}/tasks/{tid}", json={"priority": "high"})
    assert r.status_code == 200
    assert r.json()["priority"] == "high"
    assert r.json()["title"] == task["title"]


# ---------------------------------------------------------------------------
# Delete (soft)
# ---------------------------------------------------------------------------

def test_delete_task_returns_204(base_url, auth_headers, project_id):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post(f"/projects/{project_id}/tasks", json={"title": "To Delete"})
        tid = r.json()["id"]
        r2 = client.delete(f"/projects/{project_id}/tasks/{tid}")
    assert r2.status_code == 204


def test_delete_task_subsequent_get_returns_404(base_url, auth_headers, project_id):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post(f"/projects/{project_id}/tasks", json={"title": "Soft Deleted"})
        tid = r.json()["id"]
        client.delete(f"/projects/{project_id}/tasks/{tid}")
        r2 = client.get(f"/projects/{project_id}/tasks/{tid}")
    assert r2.status_code == 404


def test_delete_task_not_in_list(base_url, auth_headers, project_id):
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post(f"/projects/{project_id}/tasks", json={"title": "Gone from list"})
        tid = r.json()["id"]
        client.delete(f"/projects/{project_id}/tasks/{tid}")
        r2 = client.get(f"/projects/{project_id}/tasks")
    task_ids = [t["id"] for t in r2.json()]
    assert tid not in task_ids


# ---------------------------------------------------------------------------
# DB verification — soft delete row still exists
# ---------------------------------------------------------------------------

def test_soft_delete_row_preserved_in_db(base_url, auth_headers, project_id, db_conn):
    if db_conn is None:
        pytest.skip("DATABASE_URL not available")
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post(f"/projects/{project_id}/tasks", json={"title": "DB Soft Delete Check"})
        tid = r.json()["id"]
        client.delete(f"/projects/{project_id}/tasks/{tid}")
    with db_conn.cursor() as cur:
        cur.execute("SELECT id, deleted_at FROM tasks WHERE id = %s", (tid,))
        row = cur.fetchone()
    assert row is not None
    assert row[1] is not None  # deleted_at is set


def test_create_task_exists_in_db(base_url, auth_headers, project_id, db_conn):
    if db_conn is None:
        pytest.skip("DATABASE_URL not available")
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post(f"/projects/{project_id}/tasks", json={"title": "DB Create Check"})
    tid = r.json()["id"]
    with db_conn.cursor() as cur:
        cur.execute("SELECT id, title FROM tasks WHERE id = %s", (tid,))
        row = cur.fetchone()
    assert row is not None
    assert row[1] == "DB Create Check"


def test_update_task_reflected_in_db(base_url, auth_headers, project_id, db_conn):
    if db_conn is None:
        pytest.skip("DATABASE_URL not available")
    with httpx.Client(base_url=base_url, headers=auth_headers) as client:
        r = client.post(f"/projects/{project_id}/tasks", json={"title": "Before Update"})
        tid = r.json()["id"]
        client.patch(f"/projects/{project_id}/tasks/{tid}", json={"title": "After Update"})
    with db_conn.cursor() as cur:
        cur.execute("SELECT title FROM tasks WHERE id = %s", (tid,))
        row = cur.fetchone()
    assert row[0] == "After Update"
