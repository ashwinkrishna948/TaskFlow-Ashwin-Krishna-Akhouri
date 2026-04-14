"""Unit tests for app.models — Pydantic validation, enums, field constraints."""
import pytest
from pydantic import ValidationError

from app.models import (
    NoNullStr,
    TaskStatus,
    TaskPriority,
    PaginationParams,
    UserRegisterRequest,
    ProjectCreateRequest,
    ProjectUpdateRequest,
    TaskCreateRequest,
    TaskUpdateRequest,
)


# ---------------------------------------------------------------------------
# NoNullStr — null byte rejection
# ---------------------------------------------------------------------------

def test_no_null_str_rejects_null_byte():
    with pytest.raises(ValidationError):
        ProjectCreateRequest(name="evil\x00name")


def test_no_null_str_rejects_null_byte_in_description():
    with pytest.raises(ValidationError):
        ProjectCreateRequest(name="ok", description="bad\x00desc")


def test_no_null_str_allows_normal_string():
    p = ProjectCreateRequest(name="Normal name")
    assert p.name == "Normal name"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

def test_task_status_values():
    assert TaskStatus.todo == "todo"
    assert TaskStatus.in_progress == "in_progress"
    assert TaskStatus.done == "done"


def test_task_priority_values():
    assert TaskPriority.low == "low"
    assert TaskPriority.medium == "medium"
    assert TaskPriority.high == "high"


def test_task_create_invalid_status_raises():
    with pytest.raises(ValidationError):
        TaskCreateRequest(title="t", status="invalid_status")


def test_task_create_invalid_priority_raises():
    with pytest.raises(ValidationError):
        TaskCreateRequest(title="t", priority="critical")


# ---------------------------------------------------------------------------
# Field length limits
# ---------------------------------------------------------------------------

def test_user_name_max_length():
    with pytest.raises(ValidationError):
        UserRegisterRequest(name="x" * 201, email="a@b.com", password="password1")


def test_user_name_at_limit():
    u = UserRegisterRequest(name="x" * 200, email="a@b.com", password="password1")
    assert len(u.name) == 200


def test_project_name_max_length():
    with pytest.raises(ValidationError):
        ProjectCreateRequest(name="x" * 501)


def test_project_description_max_length():
    with pytest.raises(ValidationError):
        ProjectCreateRequest(name="ok", description="x" * 5001)


def test_task_title_max_length():
    with pytest.raises(ValidationError):
        TaskCreateRequest(title="x" * 501)


def test_task_description_max_length():
    with pytest.raises(ValidationError):
        TaskCreateRequest(title="ok", description="x" * 5001)


def test_password_min_length():
    with pytest.raises(ValidationError):
        UserRegisterRequest(name="Jane", email="j@example.com", password="short")


# ---------------------------------------------------------------------------
# PaginationParams
# ---------------------------------------------------------------------------

def test_pagination_offset_first_page():
    p = PaginationParams(page=1, page_size=20)
    assert p.offset == 0


def test_pagination_offset_second_page():
    p = PaginationParams(page=2, page_size=20)
    assert p.offset == 20


def test_pagination_offset_custom_size():
    p = PaginationParams(page=3, page_size=10)
    assert p.offset == 20


def test_pagination_page_size_max():
    with pytest.raises(ValidationError):
        PaginationParams(page=1, page_size=101)


def test_pagination_page_min():
    with pytest.raises(ValidationError):
        PaginationParams(page=0)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

def test_task_create_defaults():
    t = TaskCreateRequest(title="My task")
    assert t.status == TaskStatus.todo
    assert t.priority == TaskPriority.medium
    assert t.assignee_id is None
    assert t.due_date is None


def test_task_update_all_optional():
    t = TaskUpdateRequest()
    assert t.title is None
    assert t.status is None
    assert t.priority is None
