"""Unit tests for project_service and task_service — logic tested with mock DB connections."""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")


# ---------------------------------------------------------------------------
# Helpers to build mock rows
# ---------------------------------------------------------------------------

def _mock_row(**kwargs):
    row = MagicMock()
    row._mapping = kwargs
    return row


def _mock_result(*rows):
    result = MagicMock()
    result.fetchone.return_value = rows[0] if rows else None
    result.fetchall.return_value = list(rows)
    result.__iter__ = MagicMock(return_value=iter(rows))
    return result


# ---------------------------------------------------------------------------
# VALID_TRANSITIONS
# ---------------------------------------------------------------------------

def test_valid_transitions_structure():
    from app.services.task_service import VALID_TRANSITIONS
    assert "todo" in VALID_TRANSITIONS
    assert "in_progress" in VALID_TRANSITIONS
    assert "done" in VALID_TRANSITIONS
    assert "in_progress" in VALID_TRANSITIONS["todo"]
    assert "done" in VALID_TRANSITIONS["todo"]
    assert "todo" in VALID_TRANSITIONS["in_progress"]
    assert "done" in VALID_TRANSITIONS["in_progress"]
    assert "todo" in VALID_TRANSITIONS["done"]
    assert "in_progress" in VALID_TRANSITIONS["done"]


# ---------------------------------------------------------------------------
# project_service.create_project
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_project_returns_dict():
    from app.services.project_service import create_project

    row = _mock_row(id="proj-1", name="Test", description=None, owner_id="user-1", created_at="2026-01-01")
    conn = AsyncMock()
    conn.execute.return_value = _mock_result(row)

    result = await create_project(conn, "user-1", "Test", None)
    assert result["id"] == "proj-1"
    assert result["name"] == "Test"


# ---------------------------------------------------------------------------
# project_service._require_owner
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_require_owner_raises_404_when_not_found():
    from app.services.project_service import _require_owner

    conn = AsyncMock()
    conn.execute.return_value = _mock_result()  # no row

    with pytest.raises(HTTPException) as exc_info:
        await _require_owner(conn, "proj-1", "user-1")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_require_owner_raises_403_when_not_owner():
    from app.services.project_service import _require_owner

    row = _mock_row(owner_id="other-user")
    conn = AsyncMock()
    conn.execute.return_value = _mock_result(row)

    with pytest.raises(HTTPException) as exc_info:
        await _require_owner(conn, "proj-1", "user-1")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_owner_succeeds_for_owner():
    from app.services.project_service import _require_owner

    row = _mock_row(owner_id="user-1")
    conn = AsyncMock()
    conn.execute.return_value = _mock_result(row)

    await _require_owner(conn, "proj-1", "user-1")  # should not raise


# ---------------------------------------------------------------------------
# task_service — status transition validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_task_invalid_status_transition_raises():
    """Test that updating to a non-existent status value triggers validation before the service."""
    from app.services.task_service import update_task, VALID_TRANSITIONS

    # Verify "todo" → "done" is valid (not the right test case)
    assert "done" in VALID_TRANSITIONS["todo"]

    task_row = _mock_row(
        id="task-1", status="todo", title="t", description=None,
        priority="medium", project_id="proj-1", assignee_id="user-1",
        due_date=None, created_at="2026-01-01", updated_at="2026-01-01",
        created_by="user-1", deleted_at=None, owner_id="user-1",
    )
    conn = AsyncMock()
    conn.execute.return_value = _mock_result(task_row)

    # Bypass Pydantic by passing a raw invalid string directly to the service
    with pytest.raises(HTTPException) as exc_info:
        await update_task(conn, "proj-1", "task-1", "user-1", {"status": "cancelled"})
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_update_task_invalid_transition_same_status_is_no_op():
    from app.services.task_service import update_task

    task_row = _mock_row(
        id="task-1", status="todo", title="t", description=None,
        priority="medium", project_id="proj-1", assignee_id="user-1",
        due_date=None, created_at="2026-01-01", updated_at="2026-01-01",
        created_by="user-1", deleted_at=None, owner_id="user-1",
    )
    update_row = _mock_row(
        id="task-1", status="todo", title="t", description=None,
        priority="medium", project_id="proj-1", assignee_id="user-1",
        due_date=None, created_at="2026-01-01", updated_at="2026-01-01",
        created_by="user-1", deleted_at=None,
    )
    conn = AsyncMock()
    conn.execute.side_effect = [
        _mock_result(task_row),   # _require_task_access
        _mock_result(update_row), # UPDATE
    ]

    result = await update_task(conn, "proj-1", "task-1", "user-1", {"status": "todo"})
    assert result["status"] == "todo"


# ---------------------------------------------------------------------------
# task_service.delete_task — authorization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_task_raises_404_when_not_found():
    from app.services.task_service import delete_task

    conn = AsyncMock()
    conn.execute.return_value = _mock_result()  # no row

    with pytest.raises(HTTPException) as exc_info:
        await delete_task(conn, "proj-1", "task-1", "user-1")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_task_raises_403_when_neither_owner_nor_creator():
    from app.services.task_service import delete_task

    row = _mock_row(id="task-1", created_by="other-user", owner_id="also-other")
    conn = AsyncMock()
    conn.execute.return_value = _mock_result(row)

    with pytest.raises(HTTPException) as exc_info:
        await delete_task(conn, "proj-1", "task-1", "user-1")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_delete_task_succeeds_for_project_owner():
    from app.services.task_service import delete_task

    row = _mock_row(id="task-1", created_by="other-user", owner_id="user-1")
    conn = AsyncMock()
    conn.execute.side_effect = [
        _mock_result(row),   # SELECT
        _mock_result(),      # UPDATE (soft delete)
    ]

    await delete_task(conn, "proj-1", "task-1", "user-1")  # should not raise


@pytest.mark.asyncio
async def test_delete_task_succeeds_for_task_creator():
    from app.services.task_service import delete_task

    row = _mock_row(id="task-1", created_by="user-1", owner_id="project-owner")
    conn = AsyncMock()
    conn.execute.side_effect = [
        _mock_result(row),   # SELECT
        _mock_result(),      # UPDATE (soft delete)
    ]

    await delete_task(conn, "proj-1", "task-1", "user-1")  # should not raise


# ---------------------------------------------------------------------------
# task_service._require_task_access
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_require_task_access_raises_404_when_not_found():
    from app.services.task_service import _require_task_access

    conn = AsyncMock()
    conn.execute.return_value = _mock_result()  # no row

    with pytest.raises(HTTPException) as exc_info:
        await _require_task_access(conn, "proj-1", "task-1", "user-1")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_require_task_access_returns_dict_when_found():
    from app.services.task_service import _require_task_access

    row = _mock_row(id="task-1", title="t", status="todo", priority="medium",
                    project_id="p-1", assignee_id="user-1", description=None,
                    due_date=None, created_at="2026-01-01", updated_at="2026-01-01",
                    created_by="user-1", deleted_at=None)
    conn = AsyncMock()
    conn.execute.return_value = _mock_result(row)

    task = await _require_task_access(conn, "proj-1", "task-1", "user-1")
    assert task["id"] == "task-1"
