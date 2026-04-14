from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field


def _reject_null_bytes(v: object) -> object:
    if isinstance(v, str) and "\x00" in v:
        raise ValueError("null bytes are not allowed in text fields")
    return v


NoNullStr = Annotated[str, BeforeValidator(_reject_null_bytes)]


class TaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class UserRegisterRequest(BaseModel):
    name: NoNullStr = Field(max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=1000)


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=1000)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

class ProjectCreateRequest(BaseModel):
    name: NoNullStr = Field(max_length=500)
    description: Optional[NoNullStr] = Field(default=None, max_length=5000)


class ProjectUpdateRequest(BaseModel):
    name: Optional[NoNullStr] = Field(default=None, max_length=500)
    description: Optional[NoNullStr] = Field(default=None, max_length=5000)


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    owner_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectWithTasksResponse(ProjectResponse):
    tasks: list["TaskResponse"] = []


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class TaskCreateRequest(BaseModel):
    title: NoNullStr = Field(max_length=500)
    description: Optional[NoNullStr] = Field(default=None, max_length=5000)
    status: TaskStatus = TaskStatus.todo
    priority: TaskPriority = TaskPriority.medium
    assignee_id: Optional[UUID] = None
    due_date: Optional[date] = None


class TaskUpdateRequest(BaseModel):
    title: Optional[NoNullStr] = Field(default=None, max_length=500)
    description: Optional[NoNullStr] = Field(default=None, max_length=5000)
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assignee_id: Optional[UUID] = None
    due_date: Optional[date] = None


class TaskResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    status: TaskStatus
    priority: TaskPriority
    project_id: UUID
    assignee_id: Optional[UUID]
    due_date: Optional[date]
    created_at: datetime
    updated_at: datetime
    created_by: UUID

    model_config = ConfigDict(from_attributes=True)


ProjectWithTasksResponse.model_rebuild()
